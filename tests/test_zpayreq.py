"""Unit and end-to-end ZIP-321 payment request tests."""
import importlib.machinery
import importlib.util
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
loader = importlib.machinery.SourceFileLoader("zpayreq", str(ROOT / "zpayreq"))
spec = importlib.util.spec_from_loader("zpayreq", loader)
module = importlib.util.module_from_spec(spec)
loader.exec_module(module)

T = "t1goiSyw2JinFCmUnfiwwp72LEZzD42TyYu"
T3 = "t3ev37Q2uL1sfTsiJQJiWJoFzQpDhmnUwYo"
SAPLING = "zs1cpf4prtmnqpg6x2ngcrwelu9a39z9l9lqukq9fwagnaqrknk34a7n3szwxpjuxfjdxkuzykel53"
U = "u1cysntkxwt0h4sahp7rhj7u27pgc2ga7685ekf65g0d5ht5glkfm4zkumhvkd2zg2pdrgv3mrwq2x3vw2yl5u7zef3cr2nqwrzu7v2dsa"
TESTNET_T = "tmEZhbWHTpdKMw5it8YDspUXSMGQyFwovpU"
TESTNET_S = "ztestsapling10yy2ex5dcqkclhc7z7yrnjq2z6feyjad56ptwlfgmy77dmaqqrl9gyhprdx59qgmsnyfska2kez"


def run(*args):
    return subprocess.run([sys.executable, str(ROOT / "zpayreq"), *args], capture_output=True, text=True)


class PaymentRequestTests(unittest.TestCase):
    def assert_error(self, code, args, status):
        proc = run(*args)
        self.assertEqual(proc.returncode, status, (args, proc.stderr))
        self.assertEqual(proc.stdout, "", (args, proc.stdout))
        self.assertTrue(proc.stderr.startswith(code + ":"), (args, proc.stderr))

    def test_valid_transparent_mainnet_and_testnet(self):
        for addr in (T, T3, TESTNET_T):
            with self.subTest(addr=addr):
                proc = run(addr, "1.25000000")
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(proc.stdout, f"zcash:{addr}?amount=1.25\n")
                self.assertEqual(proc.stderr, "")

    def test_valid_sapling(self):
        for addr in (SAPLING, TESTNET_S):
            proc = run(addr, "0.00000001", "--require-shielded")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout, f"zcash:{addr}?amount=0.00000001\n")

    def test_valid_unified(self):
        for args in ((U, "42"), (U, "42", "--require-shielded"), (U, "42", "--shielded-only")):
            proc = run(*args)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout, f"zcash:{U}?amount=42\n")

    def test_amount_canonicalization(self):
        for raw, canonical in (
            ("00050.00", "50"), ("0.50000000", "0.5"), ("000.00000001", "0.00000001"),
            ("21000000.00000000", "21000000"), ("001.0010", "1.001"), ("1", "1"),
            ("0.0001", "0.0001"), ("000001", "1"),
        ):
            with self.subTest(raw=raw):
                self.assertEqual(module.validate_amount(raw), canonical)

    def test_invalid_addresses(self):
        for bad in ("", "not-an-address", T[:-1] + "1", SAPLING[:-1] + "q", U[:-1] + "p", T + " ", "zs1bad", "u1bad"):
            with self.subTest(bad=bad):
                self.assert_error("INVALID_ADDRESS", [bad, "1"], 10)

    def test_shielded_requirement(self):
        for addr in (T, T3, TESTNET_T):
            for flag in ("--require-shielded", "--shielded-required", "--shielded-only"):
                self.assert_error("SHIELDED_REQUIRED", [addr, "1", flag], 11)

    def test_invalid_amount_syntax(self):
        for text in ("NaN", "nan", "inf", "Infinity", "1e-3", "+1", "1.", ".5", "1,000", " 1", "1 ", "", "1_000", "1/2", "0x01", "☃", "--5", "5.1.1"):
            with self.subTest(text=text):
                self.assert_error("INVALID_AMOUNT", [SAPLING, text], 20)

    def test_nonpositive_amount(self):
        for text in ("0", "0.00000000", "0000", "-1", "-0", "-0.00001", "-9999999.23"):
            with self.subTest(text=text):
                self.assert_error("NON_POSITIVE_AMOUNT", [SAPLING, text], 21)

    def test_precision(self):
        for text in ("0.000000001", "1.000000000", "1.234567890", "000.123456789"):
            with self.subTest(text=text):
                self.assert_error("INVALID_PRECISION", [SAPLING, text], 22)

    def test_oversized_amount(self):
        for text in ("21000000.00000001", "21000001", "999999999999999999999999999"):
            with self.subTest(text=text):
                self.assert_error("AMOUNT_TOO_LARGE", [SAPLING, text], 23)

    def test_no_funds_sent(self):
        # Pure formatter: output is a URI; no payment network operation.
        uri = module.build_uri(T, "0.01")
        self.assertEqual(uri, f"zcash:{T}?amount=0.01")


if __name__ == "__main__":
    unittest.main()
