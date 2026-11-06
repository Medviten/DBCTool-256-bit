// Copyright (c) 2025 DBCTool
//
// DBCTool is licensed under the MIT License.
// See the LICENSE file for details.

package main

import (
    "encoding/binary"
    "fmt"
    "log"
    "strconv"
)

// RaceMask is a 256-bit race mask, bit (race - 1) set per race, stored as four 64-bit words (races 1-64 first).
//
// In a DBC file it takes 32 bytes: 8 little-endian uint32 fields. Stock 3.3.5 DBCs hold a single uint32,
// which LoadDBC still reads and export writes with race_mask_bits = 32. In SQL it is four BIGINT UNSIGNED columns: the field's own name holds races 1-64,
// followed by <name>_2, <name>_3 and <name>_4, so SQL bitwise math keeps working on each column.
type RaceMask [raceMaskWords]uint64

const (
    raceMaskWords         = 4
    raceMaskDBCFields     = 8
    raceMaskDBCSize       = raceMaskDBCFields * 4
    legacyRaceMaskDBCSize = 4
)

// raceMaskBits is the layout export writes and import creates tables with: 256 (8 DBC fields, four BIGINT UNSIGNED
// columns) or 32 (the stock single field and signed INT column, races 1-32 only). Reading a DBC accepts both
// layouts whatever this is. Set from options.race_mask_bits or --race-mask-bits.
var raceMaskBits = 256

// setRaceMaskBits validates and applies a race mask layout; 0 keeps the current one.
func setRaceMaskBits(bits int) error {
    switch bits {
    case 0:
        return nil
    case 32, 256:
        raceMaskBits = bits
        return nil
    }
    return fmt.Errorf("race mask bits must be 32 or 256, got %d", bits)
}

// raceMaskOutFields and raceMaskOutSize give the DBC layout export writes.
func raceMaskOutFields() int {
    if raceMaskBits == 32 {
        return 1
    }
    return raceMaskDBCFields
}

func raceMaskOutSize() int {
    return raceMaskOutFields() * 4
}

// raceMaskSQLColumns returns the SQL columns of one race mask element in the current layout.
func raceMaskSQLColumns(name string) []string {
    if raceMaskBits == 32 {
        return []string{name}
    }
    return raceMaskColumns(name)
}

// fitsLegacy reports whether the mask has no bits above race 32.
func (m RaceMask) fitsLegacy() bool {
    return m[0]>>32 == 0 && m[1] == 0 && m[2] == 0 && m[3] == 0
}

// legacyValue returns races 1-32 as the signed value of a stock INT column.
func (m RaceMask) legacyValue() int32 {
    return int32(uint32(m[0]))
}

// raceMask32ChecksumSalt is mixed into the export checksum of tables with race masks in the 32-bit layout.
const raceMask32ChecksumSalt = 0x52414345_4d534b33 // "RACEMSK3"

// metaHasRaceMask reports whether a meta has any racemask field.
func metaHasRaceMask(meta MetaFile) bool {
    for _, f := range meta.Fields {
        if f.Type == "racemask" {
            return true
        }
    }
    return false
}

// warnTruncated reports masks that lost races above 32 when written in the 32-bit layout.
func warnTruncated(what string, count int) {
    if count > 0 {
        log.Printf("WARNING: %s: %d race mask(s) had races above 32, dropped by race_mask_bits = 32", what, count)
    }
}

// raceMaskColumns returns the SQL column names of one race mask element, lowest races first.
func raceMaskColumns(name string) []string {
    cols := make([]string, raceMaskWords)
    cols[0] = name
    for w := 1; w < raceMaskWords; w++ {
        cols[w] = fmt.Sprintf("%s_%d", name, w+1)
    }
    return cols
}

// readRaceMask reads a 32-byte race mask from a DBC record.
func readRaceMask(data []byte) RaceMask {
    var mask RaceMask
    for w := 0; w < raceMaskWords; w++ {
        low := binary.LittleEndian.Uint32(data[w*8 : w*8+4])
        high := binary.LittleEndian.Uint32(data[w*8+4 : w*8+8])
        mask[w] = uint64(high)<<32 | uint64(low)
    }
    return mask
}

// readLegacyRaceMask reads a 4-byte race mask (races 1-32) from a stock DBC record.
func readLegacyRaceMask(data []byte) RaceMask {
    return RaceMask{uint64(binary.LittleEndian.Uint32(data[0:4]))}
}

// putRaceMaskOut writes a race mask in the layout export writes (raceMaskOutSize bytes).
func putRaceMaskOut(buf []byte, mask RaceMask) {
    if raceMaskBits == 32 {
        binary.LittleEndian.PutUint32(buf[0:4], uint32(mask[0]))
        return
    }
    putRaceMask(buf, mask)
}

// putRaceMask writes a race mask as 8 little-endian uint32 fields into buf (32 bytes).
func putRaceMask(buf []byte, mask RaceMask) {
    for w := 0; w < raceMaskWords; w++ {
        binary.LittleEndian.PutUint32(buf[w*8:w*8+4], uint32(mask[w]))
        binary.LittleEndian.PutUint32(buf[w*8+4:w*8+8], uint32(mask[w]>>32))
    }
}

// String returns the shortest 0x-prefixed hex form, e.g. 0x44d.
func (m RaceMask) String() string {
    w := raceMaskWords - 1
    for w > 0 && m[w] == 0 {
        w--
    }
    s := fmt.Sprintf("0x%x", m[w])
    for w--; w >= 0; w-- {
        s += fmt.Sprintf("%016x", m[w])
    }
    return s
}

// toUint64 reads a race mask word column. Negative values can only come from tables still holding the old
// signed INT race mask columns, so they keep their 32-bit pattern (-1 stays races 1-32).
func toUint64(raw []interface{}, cols []string, name string) uint64 {
    for i, col := range cols {
        if col == name && raw[i] != nil {
            switch v := raw[i].(type) {
            case int64:
                if v < 0 {
                    return uint64(uint32(v))
                }
                return uint64(v)
            case uint64:
                return v
            case []byte:
                return parseUint64(string(v))
            case string:
                return parseUint64(v)
            }
        }
    }
    return 0
}

func parseUint64(s string) uint64 {
    if n, err := strconv.ParseUint(s, 10, 64); err == nil {
        return n
    }
    if n, err := strconv.ParseInt(s, 10, 32); err == nil {
        return uint64(uint32(n))
    }
    return 0
}
