// Copyright (c) 2025 DBCTool
//
// DBCTool is licensed under the MIT License.
// See the LICENSE file for details.

package main

import (
    "encoding/binary"
    "fmt"
    "strconv"
)

// RaceMask is a 256-bit race mask, bit (race - 1) set per race, stored as four 64-bit words (races 1-64 first).
//
// In a DBC file it takes 32 bytes: 8 little-endian uint32 fields. Stock 3.3.5 DBCs hold a single uint32,
// which LoadDBC still reads. In SQL it is four BIGINT UNSIGNED columns: the field's own name holds races 1-64,
// followed by <name>_2, <name>_3 and <name>_4, so SQL bitwise math keeps working on each column.
type RaceMask [raceMaskWords]uint64

const (
    raceMaskWords         = 4
    raceMaskDBCFields     = 8
    raceMaskDBCSize       = raceMaskDBCFields * 4
    legacyRaceMaskDBCSize = 4
)

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
