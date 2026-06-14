# py_qtsql

QtSQL XOR Demo is a small PyQt6 sample application for experimenting with a local
SQLite database, simple UI workflows, and reversible byte-level transformations.

The app stores records in `./data/main_data.db` with this shape:
- `uid`
- `number`
- `text`
- `note`
- `key1`
- `key2`

The `text` field can be stored as raw XOR hex and decoded in the table with the
active hex key from `.env`. The UI includes basic key handling, record creation,
row editing, deletion with confirmation, table filtering, and a right-click row
menu for record actions.

---

## Educational Scope

This project is a demo, not a security tool. XOR is used here because it is easy
to inspect, easy to reverse, and useful for understanding how byte operations
and hex encoding work.

> "Security by obscurity is like using XOR for encryption—without a strong key,
> it's just a false sense of safety. True security relies on robust, well-tested
> methods. #CyberSecurity #Encryption"

For real-world security, use modern authenticated encryption and established
cryptographic libraries instead of custom XOR-based schemes.
