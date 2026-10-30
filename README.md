# zpayreq — ZIP-321 Payment-Request Builder

A minimal Python 3 CLI that **builds** Zcash ZIP-321 single-recipient payment-request URIs. No Zcash wallet, network, dependencies, secrets, or funds are needed. It **never broadcasts transactions**.

## Usage

```sh
./zpayreq <address> <amount> [--require-shielded]
```

Examples:

```sh
./zpayreq t1goiSyw2JinFCmUnfiwwp72LEZzD42TyYu 1.25000000
# zcash:t1goiSyw2JinFCmUnfiwwp72LEZzD42TyYu?amount=1.25

./zpayreq zs1cpf4prtmnqpg6x2ngcrwelu9a39z9l9lqukq9fwagnaqrknk34a7n3szwxpjuxfjdxkuzykel53 0.00000001 --require-shielded
# zcash:zs1cpf4prtmnqpg6x2ngcrwelu9a39z9l9lqukq9fwagnaqrknk34a7n3szwxpjuxfjdxkuzykel53?amount=0.00000001

./zpayreq t1goiSyw2JinFCmUnfiwwp72LEZzD42TyYu 1 --require-shielded
# SHIELDED_REQUIRED: Transparent-only addresses cannot satisfy the shielded requirement.
# Exit code: 11
```

Successful calls print **one standard ZIP-321 URI** on stdout and exit 0. Failures print an actionable **stable error code** and message on stderr, leave stdout empty, and exit nonzero.

## Validation and error codes

| Code | Exit | Meaning |
|---|---:|---|
| `USAGE_ERROR` | 2 | Missing or extra positional arguments |
| `INVALID_ADDRESS` | 10 | Malformed Zcash address, unsupported prefix/encoding, or invalid checksum |
| `SHIELDED_REQUIRED` | 11 | Transparent-only address used with `--require-shielded` |
| `INVALID_AMOUNT` | 20 | Malformed decimal, NaN, Infinity, exponent, extra separators, whitespace or sign |
| `NON_POSITIVE_AMOUNT` | 21 | Zero or negative amount |
| `INVALID_PRECISION` | 22 | More than eight fractional decimal digits |
| `AMOUNT_TOO_LARGE` | 23 | Amount greater than 21,000,000 ZEC |

Supported address encodings: transparent (Base58Check), Sapling (Bech32), and Unified (Bech32m + ZIP-316 F4Jumble). Shielded mode accepts Sapling and valid Unified Addresses containing shielded receivers. Sprout and malformed addresses are rejected. The address validation core is reused from my [Zcash address checker project](https://github.com/Ay-obami/zaddrcheck).

ZEC amounts are parsed using Python's `decimal.Decimal` and a strict lexical grammar. There is **no binary floating-point rounding**. Output uses a canonical decimal representation (e.g. `0001.23000000` becomes `1.23`), with a maximum of eight fractional digits and a maximum total amount of 21 million ZEC.

This CLI validates address **encodings**. It does not check whether an address belongs to a particular wallet or whether an actual wallet will accept it.

## Tests

Run locally:

```sh
python3 -m unittest discover -s tests -v
```

GitHub Actions automatically runs all 11 test groups on the default `main` branch and on pull requests, including real public transparent, Sapling, Unified and testnet address fixtures, success cases and every documented error class. No live funds are used.

## Specification

- [ZIP 321 — Payment Request URIs](https://zips.z.cash/zip-0321)
- [ZIP 316 — Unified Addresses](https://zips.z.cash/zip-0316)
