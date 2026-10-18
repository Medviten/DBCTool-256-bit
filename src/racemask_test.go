// Copyright (c) 2025 DBCTool
//
// DBCTool is licensed under the MIT License.
// See the LICENSE file for details.

package main

import (
    "bytes"
    "encoding/binary"
    "os"
    "path/filepath"
    "testing"
)

var testMeta = MetaFile{
    File: "Test.dbc",
    Fields: []FieldMeta{
        {Name: "id", Type: "uint32"},
        {Name: "race_mask", Type: "racemask"},
        {Name: "rep_race_mask", Type: "racemask", Count: 2},
        {Name: "class_mask", Type: "uint32"},
    },
}

// buildDBC assembles a DBC file from little-endian uint32 fields per record.
func buildDBC(fieldsPerRecord int, records [][]uint32) []byte {
    var buf bytes.Buffer
    buf.WriteString("WDBC")
    binary.Write(&buf, binary.LittleEndian, uint32(len(records)))
    binary.Write(&buf, binary.LittleEndian, uint32(fieldsPerRecord))
    binary.Write(&buf, binary.LittleEndian, uint32(fieldsPerRecord*4))
    binary.Write(&buf, binary.LittleEndian, uint32(1)) // string block: a single null byte
    for _, rec := range records {
        for _, v := range rec {
            binary.Write(&buf, binary.LittleEndian, v)
        }
    }
    buf.WriteByte(0)
    return buf.Bytes()
}

func loadTestDBC(t *testing.T, data []byte, meta MetaFile) DBCFile {
    t.Helper()
    path := filepath.Join(t.TempDir(), meta.File)
    if err := os.WriteFile(path, data, 0644); err != nil {
        t.Fatal(err)
    }
    dbc, err := LoadDBC(path, meta)
    if err != nil {
        t.Fatalf("LoadDBC: %v", err)
    }
    return dbc
}

func TestLoadStockDBCWidensRaceMasks(t *testing.T) {
    // stock layout: every race mask is one uint32
    data := buildDBC(5, [][]uint32{
        {7, 1101, 690, 0xFFFFFFFF, 1535},
    })
    dbc := loadTestDBC(t, data, testMeta)

    rec := dbc.Records[0]
    if got := rec["race_mask"].(RaceMask); got != (RaceMask{1101}) {
        t.Errorf("race_mask = %v", got)
    }
    if got := rec["rep_race_mask_1"].(RaceMask); got != (RaceMask{690}) {
        t.Errorf("rep_race_mask_1 = %v", got)
    }
    if got := rec["rep_race_mask_2"].(RaceMask); got != (RaceMask{0xFFFFFFFF}) {
        t.Errorf("rep_race_mask_2 = %v (a stock -1 must stay races 1-32)", got)
    }
    if rec["class_mask"].(uint32) != 1535 {
        t.Errorf("class_mask = %v, fields after race masks are misaligned", rec["class_mask"])
    }
}

func TestWideDBCRoundTrip(t *testing.T) {
    meta := testMeta
    race100 := RaceMask{0, 1 << 35}
    all := RaceMask{^uint64(0), ^uint64(0), ^uint64(0), ^uint64(0)}

    dbc := DBCFile{
        Header: DBCHeader{
            Magic:           [4]byte{'W', 'D', 'B', 'C'},
            RecordCount:     1,
            FieldCount:      calculateFieldCount(meta),
            RecordSize:      calculateRecordSize(meta),
            StringBlockSize: 1,
        },
        Records: []Record{{
            "id":              uint32(9),
            "race_mask":       race100,
            "rep_race_mask_1": all,
            "rep_race_mask_2": RaceMask{2048, 0, 0, 1 << 63},
            "class_mask":      uint32(1),
        }},
        StringBlock: []byte{0},
    }

    if dbc.Header.FieldCount != 1+8+16+1 || dbc.Header.RecordSize != 4*(1+8+16+1) {
        t.Fatalf("header fields=%d size=%d", dbc.Header.FieldCount, dbc.Header.RecordSize)
    }

    path := filepath.Join(t.TempDir(), "wide.dbc")
    if err := WriteDBC(&dbc, &meta, path); err != nil {
        t.Fatal(err)
    }
    written, _ := os.ReadFile(path)

    // race 100 is bit 99: word 3 of the 8 uint32 fields, bit 3
    raceField := written[20+4 : 20+4+32]
    if binary.LittleEndian.Uint32(raceField[12:16]) != 1<<3 {
        t.Errorf("race 100 not stored in the 4th uint32 of the race mask: % x", raceField)
    }

    reread := loadTestDBC(t, written, meta)
    for name, want := range dbc.Records[0] {
        if got := reread.Records[0][name]; got != want {
            t.Errorf("%s = %v, want %v", name, got, want)
        }
    }

    path2 := filepath.Join(t.TempDir(), "wide2.dbc")
    if err := WriteDBC(&reread, &meta, path2); err != nil {
        t.Fatal(err)
    }
    if same, _ := compareFiles(path, path2); !same {
        t.Error("re-exported DBC differs from the original")
    }
}

func TestRaceMaskColumnsAndValues(t *testing.T) {
    cols := raceMaskColumns("reputation_race_mask_1")
    want := []string{"reputation_race_mask_1", "reputation_race_mask_1_2", "reputation_race_mask_1_3", "reputation_race_mask_1_4"}
    for i := range want {
        if cols[i] != want[i] {
            t.Errorf("column %d = %s, want %s", i, cols[i], want[i])
        }
    }

    sqlCols := []string{"a", "b", "c", "d", "e"}
    raw := []interface{}{int64(1101), uint64(1 << 63), []byte("18446744073709551615"), int64(-1), "-1"}
    expect := []uint64{1101, 1 << 63, ^uint64(0), 0xFFFFFFFF, 0xFFFFFFFF}
    for i, col := range sqlCols {
        if got := toUint64(raw, sqlCols, col); got != expect[i] {
            t.Errorf("toUint64(%v) = %d, want %d", raw[i], got, expect[i])
        }
    }

    if s := (RaceMask{}).String(); s != "0x0" {
        t.Errorf("empty mask = %s", s)
    }
    if s := (RaceMask{1101}).String(); s != "0x44d" {
        t.Errorf("1101 = %s", s)
    }
    if s := (RaceMask{1, 1}).String(); s != "0x10000000000000001" {
        t.Errorf("races 1+65 = %s", s)
    }
}

// Every meta in ../meta must parse a zeroed DBC of the size the exporter writes.
func TestMetasExportAndParseAgree(t *testing.T) {
    metas, err := filepath.Glob(filepath.Join("..", "meta", "*.meta.json"))
    if err != nil || len(metas) == 0 {
        t.Fatalf("no metas found: %v", err)
    }

    for _, metaPath := range metas {
        meta, err := LoadMeta(metaPath)
        if err != nil {
            t.Fatal(err)
        }

        size := calculateRecordSize(meta)
        data := buildDBC(0, nil)
        binary.LittleEndian.PutUint32(data[4:8], 1)
        binary.LittleEndian.PutUint32(data[8:12], calculateFieldCount(meta))
        binary.LittleEndian.PutUint32(data[12:16], size)
        record := make([]byte, size)
        data = append(data[:20], append(record, 0)...)

        if _, err := loadTestDBCErr(t, data, meta); err != nil {
            t.Errorf("%s: %v", filepath.Base(metaPath), err)
        }
    }
}

func loadTestDBCErr(t *testing.T, data []byte, meta MetaFile) (DBCFile, error) {
    path := filepath.Join(t.TempDir(), "m.dbc")
    if err := os.WriteFile(path, data, 0644); err != nil {
        t.Fatal(err)
    }
    return LoadDBC(path, meta)
}
