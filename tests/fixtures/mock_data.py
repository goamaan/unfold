"""Canned response data for tests."""

ANALYZE_RESULT = {
    "name": "test_binary",
    "language": "x86:LE:64:default",
    "compiler": "gcc",
    "image_base": "0x100000000",
    "num_functions": 42,
    "executable_format": "Mach-O",
}

FUNCTIONS_LIST = [
    {
        "name": "main",
        "address": "0x100000460",
        "size": 128,
        "is_thunk": False,
        "is_external": False,
    },
    {
        "name": "_check_password",
        "address": "0x100000520",
        "size": 256,
        "is_thunk": False,
        "is_external": False,
    },
    {
        "name": "printf",
        "address": "0x100000700",
        "size": 0,
        "is_thunk": True,
        "is_external": True,
    },
]

DECOMPILE_RESULT = {
    "name": "main",
    "address": "0x100000460",
    "decompiled": """int main(int argc, char **argv) {
    char *password;

    printf("Enter password: ");
    scanf("%s", password);

    if (_check_password(password)) {
        printf("Access granted!\\n");
        return 0;
    }

    printf("Access denied!\\n");
    return 1;
}""",
    "signature": "int main(int argc, char **argv)",
}

XREFS_TO_RESULT = [
    {
        "from_address": "0x100000480",
        "from_function": "main",
        "type": "UNCONDITIONAL_CALL",
    },
    {
        "from_address": "0x100000580",
        "from_function": "_validate_input",
        "type": "UNCONDITIONAL_CALL",
    },
]

XREFS_FROM_RESULT = [
    {
        "to_address": "0x100000520",
        "to_function": "_check_password",
        "type": "UNCONDITIONAL_CALL",
    },
    {
        "to_address": "0x100000600",
        "to_function": "printf",
        "type": "UNCONDITIONAL_CALL",
    },
]

STRINGS_RESULT = [
    {
        "address": "0x100000a00",
        "value": "Enter password: ",
        "length": 16,
    },
    {
        "address": "0x100000a10",
        "value": "Access granted!",
        "length": 15,
    },
    {
        "address": "0x100000a20",
        "value": "Access denied!",
        "length": 14,
    },
]

IMPORTS_EXPORTS_RESULT = {
    "imports": [
        {
            "name": "printf",
            "namespace": "libc",
            "type": "FUNCTION",
        },
        {
            "name": "scanf",
            "namespace": "libc",
            "type": "FUNCTION",
        },
    ],
    "exports": [
        {
            "name": "main",
            "address": "0x100000460",
        },
        {
            "name": "_check_password",
            "address": "0x100000520",
        },
    ],
}

RENAME_RESULT = {
    "old_name": "FUN_100000520",
    "new_name": "validate_password",
    "address": "0x100000520",
}

READ_BYTES_RESULT = {
    "address": "0x100000460",
    "count": 64,
    "hex": "55 48 89 e5 48 83 ec 20 89 7d fc 48 89 75 f0 48 8d 3d 91 00 00 00 b0 00 e8 10 00 00 00 48 8d 3d 92 00 00 00 48 8d 75 e8 b0 00 e8 00 00 00 00 48 8d 7d e8 e8 00 00 00 00 85 c0 74 0c",
    "ascii": "UH..H.. ..}.H.u.H...... ...H...H.u. ...H.}.....t.",
}
