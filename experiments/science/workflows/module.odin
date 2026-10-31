package module

ABI :: #config(ABI, 1)
VERSION :: #config(VERSION, 1)
FACTOR :: #config(FACTOR, 2)

@(export)
gaia_abi :: proc "c" () -> i64 {return ABI}
@(export)
gaia_version :: proc "c" () -> i64 {return VERSION}
@(export)
gaia_apply :: proc "c" (input: i64, state: ^i64) -> i64 {
    state^+=VERSION
    return input*FACTOR+state^
}
