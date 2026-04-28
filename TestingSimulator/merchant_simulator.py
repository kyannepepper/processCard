import argparse
import requests
import json
import random
import csv
import os
import sys
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock

# ──────────────────────────────────────────────
# CONFIG
# ──────────────────────────────────────────────
# POSTs here → API Gateway → your processCard Lambda → DynamoDB TransactionLog (or TRANSACTION_TABLE).
# Override without editing: export MERCHANT_SIMULATOR_API_URL="https://YOUR_ID.execute-api.REGION.amazonaws.com/..."
API_URL = os.environ.get(
    "MERCHANT_SIMULATOR_API_URL",
    "https://eniunn0qta.execute-api.us-west-2.amazonaws.com/default/processCard",
)
LOG_FILE = "transaction_log.txt"

# (connect seconds, read seconds). Lambda + bank retries can exceed 30s; 15s read often times out.
REQUEST_TIMEOUT = (15, 120)

MERCHANTS = [
    ("Tifinys Creperie",          "xGl2zcPA"),
    ("Dutchmans Market",          "hIhksw4s"),
    ("Sweet Rolled Tacos",        "W71AnrQu"),
    ("Cafe Rio",                  "GMuOikG4"),
    ("Judds Store",               "U8et7kOX"),
    ("Cliffside Restaurant",      "hiKzn4GE"),
    ("Bear Paw Cafe",             "0PDOt87g"),
    ("Sues Pet Castle",           "CUQpt2hi"),
    ("Contact Climbing",          "BqzXGsPJ"),
    ("Fiiz Drinks",               "xRcMVZt5"),
    ("Nielsens Frozen Custard",   "nvfeNWrn"),
    ("Viva Chicken",              "xPOMrAu2"),
    ("Riggattis Pizza",           "9rhu9xjT"),
    ("Tagg and Go Car Wash",      "9e25AhO8"),
    ("gigi gelati",               "IXNDePt6"),
    ("Costco",                    "DZXBV92s"),
    ("Mortys Cafe",               "FjPVlUR4"),
    ("Bishops Grill",             "szZRz8oe"),
    ("Veyo Pies",                 "WjY3Fj1L"),
    ("Angelicas Mexican Grill",   "sIwVMwzF"),
    ("Xetava Gardens Cafe",       "ri47FJqo"),
    ("Benjas Thai Sushi",         "febuSu6O"),
    ("FeelLove Coffee",           "MDSHVulj"),
    ("Teriyaki Grill",            "qi3vvwtv"),
    ("Desert Rat",                "GgnRlH67"),
    ("Red Rock Roasting Co",      "8aeu90dy"),
    ("Pica Rica BBQ",             "vdMGy7IJ"),
    ("Georges Corner Restaurant", "rGtsiE0e"),
    ("Painted Pony",              "QFhahv4K"),
    ("Sakura Japanese Steakhouse","5yGuXhvV"),
    ("Pizza Factory",             "PPBqnohw"),
    ("Big Shots Golf",            "1wgN5E1t"),
    ("Zion Brewery",              "RTwJShn1"),
    ("Red Rock Bicycle",          "9KqkBtAn"),
    ("Sol Foods",                 "m39ShvHl"),
    ("Tommys Express Car Wash",   "vd8vwysf"),
    ("Arctic Circle",             "OCmngQJ4"),
    ("Costa Vida",                "AzFM4BXv"),
    ("Utah Tech Campus Bookstore","ISDKxbCF"),
    ("Swig",                      "GVkgKk5O"),
    ("Smiths",                    "TlAnbSU1"),
    ("Irmitas Casita",            "9uPWL3S7"),
    ("Cappellettis",              "U55VhFuk"),
    ("Zion Outfitters",           "RVKwjpQs"),
    ("Lins",                      "zkkn0n6M"),
    ("Station 2 Bar",             "EoAv62Cr"),
    ("Taco Amigo",                "BsM86wrq"),
    ("Wood Ash Rye",              "QAJr8xhB"),
    ("Walmart",                   "260fZojB"),
    ("Rancheritos Mexican Food",  "g0EleGLo"),
]

# Default skewed distributions (so graphs aren't uniform).
# You can tweak these lists (or add CLI flags) to change the mix.
DEFAULT_BANK_WEIGHTS = {
    "Jeffs Bank": 40,
    "Tophers Bank": 25,
    "Wild West Bank": 15,
    "CaliBear": 10,
    "Corbin Bank": 7,
    "Jank Bank": 3,
}

# A few merchants heavily represented, most lightly represented.
DEFAULT_MERCHANT_WEIGHTS = {
    "Walmart": 35,
    "Costco": 25,
    "Smiths": 20,
    "Swig": 15,
    "Cafe Rio": 12,
    "Arctic Circle": 10,
}

# Merchant bank info (used in every request)
MERCHANT_BANK      = "Jeffs Bank"
MERCHANT_BANK_ACCT = "4545454545454545"

CARD_TYPES = ["debit", "credit"]

# Must match `make_payload` / `resolve_bank_name` in processCard.py
SUPPORTED_BANKS = [
    "Jeffs Bank",
    "Corbin Bank",
    "CaliBear",
    "Jank Bank",
    "Tophers Bank",
    "Wild West Bank",
]

# ──────────────────────────────────────────────
# LOAD ACCOUNTS FROM CSV
# ──────────────────────────────────────────────
def load_accounts(path="bank_test_accounts_all_strings.csv"):
    accounts = []
    # Try the uploads path first (Claude environment), then local
    for try_path in [
        "/mnt/user-data/uploads/bank_test_accounts_all_strings__1_.csv",
        path,
        os.path.join(os.path.dirname(__file__), path),
    ]:
        if os.path.exists(try_path):
            with open(try_path, newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    accounts.append(row)
            return accounts
    raise FileNotFoundError(f"CSV not found. Place {path} in the same folder as this script.")

# ──────────────────────────────────────────────
# HELPERS
# ──────────────────────────────────────────────
def ts():
    return datetime.now().strftime("%m:%d:%Y %H:%M:%S")

def small_amount(balance_str):
    """Return a small charge guaranteed under the balance."""
    balance = float(balance_str)
    if balance <= 0:
        return "0.50"          # will trigger insufficient funds
    cap = min(balance * 0.15, 50.0)   # at most 15 % of balance or $50
    cap = max(cap, 0.50)
    return f"{random.uniform(0.50, cap):.2f}"

def big_amount(balance_str):
    """Return an amount well over the balance to force insufficient funds."""
    balance = float(balance_str)
    return f"{balance + random.uniform(50, 200):.2f}"

def send(payload, label):
    """POST payload, return (label, payload_str, response_str)."""
    try:
        r = requests.post(API_URL, json=payload, timeout=REQUEST_TIMEOUT)
        try:
            body = r.json()
            resp_str = json.dumps(body)
        except Exception:
            resp_str = r.text
        return label, json.dumps(payload), resp_str
    except requests.exceptions.RequestException as e:
        return label, json.dumps(payload), f"CONNECTION ERROR: {e}"

def log(f, label, payload_str, response_str):
    f.write("-----------------\n")
    f.write(f"Test Case : {label}\n")
    f.write(f"Timestamp : {ts()}\n")
    f.write(f"Request   : {payload_str}\n")
    f.write(f"Response  : {response_str}\n")
    f.write("-----------------\n\n")
    print(f"[{label}] → {response_str[:120]}")


def _weighted_choice(items, weights):
    return random.choices(items, weights=weights, k=1)[0]


def choose_bank(bank_weights=None):
    bank_weights = bank_weights or DEFAULT_BANK_WEIGHTS
    banks = list(SUPPORTED_BANKS)
    w = [int(bank_weights.get(b, 1)) for b in banks]
    return _weighted_choice(banks, w)


def choose_merchant(merchant_weights=None):
    """
    Return a (name, token) pair with skewed distribution:
    - merchants listed in merchant_weights are more likely
    - others default to weight=1
    """
    merchant_weights = merchant_weights or DEFAULT_MERCHANT_WEIGHTS
    names = [m[0] for m in MERCHANTS]
    w = [int(merchant_weights.get(n, 1)) for n in names]
    name = _weighted_choice(names, w)
    return next(m for m in MERCHANTS if m[0] == name)


def extract_message(response_str):
    """
    Best-effort parse of {"message": "..."} from the Lambda response.
    Always returns a string (for CSV reporting).
    """
    try:
        obj = json.loads(response_str)
        if isinstance(obj, dict):
            # If it's already {message: "..."} (or nested), pull message.
            if isinstance(obj.get("message"), str):
                return obj["message"]
            if isinstance(obj.get("body"), str):
                try:
                    inner = json.loads(obj["body"])
                    if isinstance(inner, dict) and isinstance(inner.get("message"), str):
                        return inner["message"]
                except Exception:
                    pass
    except Exception:
        pass
    return response_str.strip()


def run_one(i, label, payload):
    lbl, payload_str, response_str = send(payload, label)
    return i, lbl, payload, payload_str, response_str


def base_good(acct, merchant, bank="Jeffs Bank"):
    name, token = merchant
    return {
        "bank":              bank,
        "merchant_name":     name,
        "merchant_token":    token,
        "merchant_bank":     MERCHANT_BANK,
        "merchant_bank_acct":MERCHANT_BANK_ACCT,
        # Match the exact field names you're sending to the Lambda.
        "card_holder":       acct["card_holder"],
        "cc_number":         acct["card_num"],
        "card_type":         random.choice(CARD_TYPES),
        "cvv":               acct["cvv"],
        "exp_date":          acct["exp_date"],
        "amount":            small_amount(acct["balance"]),
        "card_zip":          acct["card_zip"],
        "timestamp":         ts(),
    }


# ──────────────────────────────────────────────
# BUILD TEST CASES
# ──────────────────────────────────────────────
def build_tests(accounts):
    tests = []   # list of (label, payload)

    # ── helpers ──────────────────────────────
    def rand_acct():
        return random.choice(accounts)

    def rand_merchant():
        return choose_merchant()

    # ── 5a. Good merchant token – should Approve (10 cases) ──
    for _ in range(10):
        acct = rand_acct()
        # pick an account that actually has money
        acct = next((a for a in random.sample(accounts, len(accounts))
                     if float(a["balance"]) > 10), accounts[2])
        m = rand_merchant()
        p = base_good(acct, m)
        tests.append(("GOOD_TOKEN - Approved", p))

    # ── 5a. Bad merchant token (8 cases) ──
    for _ in range(8):
        acct = rand_acct()
        m_name, _ = rand_merchant()
        p = base_good(acct, (m_name, "BADTOKEN1"))
        tests.append(("BAD_TOKEN - Merchant Not Authorized", p))

    # ── 5b. Insufficient funds (6 cases) ──
    # Sort by lowest balance and always charge way more than they have
    broke_accounts = sorted(accounts, key=lambda a: float(a["balance"]))
    for acct in broke_accounts[:6]:
        m = rand_merchant()
        p = base_good(acct, m)
        p["amount"] = f"{float(acct['balance']) + random.uniform(500, 1000):.2f}"
        tests.append(("INSUFFICIENT_FUNDS - Declined", p))

    # ── 5c-i. Bad CVV (4 cases) ──
    for _ in range(4):
        acct = rand_acct()
        m = rand_merchant()
        p = base_good(acct, m)
        p["cvv"] = "000"
        tests.append(("BAD_CVV - Declined Card Not Valid", p))

    # ── 5c-ii. Wrong expiry date (4 cases) ──
    for _ in range(4):
        acct = rand_acct()
        m = rand_merchant()
        p = base_good(acct, m)
        p["exp_date"] = "01/20"   # expired
        tests.append(("BAD_EXP_DATE - Declined Card Not Valid", p))

    # ── 5c-iii. Wrong zip code (4 cases) ──
    for _ in range(4):
        acct = rand_acct()
        m = rand_merchant()
        p = base_good(acct, m)
        p["card_zip"] = "00000"
        tests.append(("BAD_ZIP - Declined Card Not Valid", p))

    # ── 5c-iv. Wrong card holder name (4 cases) ──
    for _ in range(4):
        acct = rand_acct()
        m = rand_merchant()
        p = base_good(acct, m)
        p["customer_name"] = "Wrong Name Person"
        tests.append(("BAD_CARDHOLDER_NAME - Declined Card Not Valid", p))

    # ── 5e. Malformed / missing fields (6 cases) ──
    # Missing amount
    acct = rand_acct(); m = rand_merchant()
    p = base_good(acct, m); del p["amount"]
    tests.append(("MISSING_FIELD(amount) - Invalid Request", p))

    # Missing cc_num
    acct = rand_acct(); m = rand_merchant()
    p = base_good(acct, m); del p["cc_num"]
    tests.append(("MISSING_FIELD(cc_num) - Invalid Request", p))

    # Missing bank
    acct = rand_acct(); m = rand_merchant()
    p = base_good(acct, m); del p["bank"]
    tests.append(("MISSING_FIELD(bank) - Invalid Request", p))

    # Missing merchant_token
    acct = rand_acct(); m = rand_merchant()
    p = base_good(acct, m); del p["merchant_token"]
    tests.append(("MISSING_FIELD(merchant_token) - Invalid Request", p))

    # Completely empty body
    tests.append(("EMPTY_BODY - Invalid Request", {}))

    # Wrong bank name → Bank Not Supported
    acct = rand_acct(); m = rand_merchant()
    p = base_good(acct, m)
    p["bank"] = "Chase Bank"
    p["merchant_bank"] = "Chase Bank"
    tests.append(("UNSUPPORTED_BANK - Bank Not Supported", p))

    # ── Extra successful transactions to reach 50+ total ──
    rich_accounts = [a for a in accounts if float(a["balance"]) > 100]
    needed = max(0, 50 - len(tests))
    for _ in range(needed + 5):
        acct = random.choice(rich_accounts) if rich_accounts else rand_acct()
        m = rand_merchant()
        p = base_good(acct, m)
        tests.append(("SUFFICIENT_FUNDS - Approved", p))

    return tests


def build_assignment_bulk(accounts, total, success_ratio=0.88, seed=None):
    """
    Many transactions across all supported banks for reporting assignments.
    Mixes successes (valid payloads) with a few failure types so you can
    compute success vs decline in Excel. Shuffle order so the log is not
    grouped by outcome.
    """
    if seed is not None:
        random.seed(seed)

    def rand_merchant():
        return choose_merchant()

    rich = [a for a in accounts if float(a["balance"]) > 10]
    if not rich:
        rich = list(accounts)
    broke = sorted(accounts, key=lambda a: float(a["balance"]))

    tests = []
    n_success = int(round(total * success_ratio))
    n_success = max(0, min(total, n_success))
    n_fail = total - n_success

    for _ in range(n_success):
        bank = choose_bank()
        acct = random.choice(rich)
        m = rand_merchant()
        p = base_good(acct, m, bank)
        tests.append(("ASSIGNMENT - Approved", p))

    fail_kinds = ["cvv", "funds", "token"]
    for _ in range(n_fail):
        bank = choose_bank()
        acct = random.choice(accounts)
        m = rand_merchant()
        kind = random.choice(fail_kinds)
        if kind == "cvv":
            p = base_good(acct, m, bank)
            p["cvv"] = "000"
            tests.append(("ASSIGNMENT - BAD_CVV", p))
        elif kind == "funds":
            low = broke[0] if broke else acct
            p = base_good(low, m, bank)
            p["amount"] = f"{float(low['balance']) + random.uniform(500, 1000):.2f}"
            tests.append(("ASSIGNMENT - INSUFFICIENT_FUNDS", p))
        else:
            m_name, _ = m
            p = base_good(acct, (m_name, "BADTOKEN1"), bank)
            tests.append(("ASSIGNMENT - BAD_TOKEN", p))

    random.shuffle(tests)
    return tests


# ──────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="POST simulated card transactions to the class API."
    )
    parser.add_argument(
        "--assignment",
        action="store_true",
        help="Send many transactions across all supported banks (for reporting homework).",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=500,
        metavar="N",
        help="With --assignment: number of transactions to send (default: 500).",
    )
    parser.add_argument(
        "--success-ratio",
        type=float,
        default=0.88,
        metavar="P",
        help="With --assignment: fraction that should be valid success payloads (0–1).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Optional RNG seed for reproducible assignment runs.",
    )
    parser.add_argument(
        "--out-csv",
        default="results.csv",
        help="Write per-transaction rows to this CSV (default: results.csv).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=10,
        help="Concurrent requests to run in parallel (default: 10). Use 1 for sequential.",
    )
    args = parser.parse_args()

    accounts = load_accounts()
    if args.assignment:
        tests = build_assignment_bulk(
            accounts,
            args.count,
            success_ratio=args.success_ratio,
            seed=args.seed,
        )
    else:
        tests = build_tests(accounts)

    print(f"\n{'='*60}")
    print(f"  Merchant Transaction Simulator")
    print(f"  Endpoint : {API_URL}")
    print(f"  Tests    : {len(tests)}")
    print(f"  Log file : {LOG_FILE}")
    print(f"  HTTP timeout (connect, read): {REQUEST_TIMEOUT}s — first call can be slow (cold start).")
    print(f"{'='*60}\n")

    out_csv_path = args.out_csv
    with open(LOG_FILE, "w") as f, open(out_csv_path, "w", newline="") as csv_f:
        writer = csv.DictWriter(
            csv_f,
            fieldnames=["run_ts", "i", "label", "bank", "merchant_name", "message"],
        )
        writer.writeheader()
        csv_f.flush()

        f.write(f"Transaction Simulator Log\n")
        f.write(f"Run started : {ts()}\n")
        f.write(f"Endpoint    : {API_URL}\n")
        f.write(f"Total tests : {len(tests)}\n\n")

        try:
            lock = Lock()
            total = len(tests)
            workers = max(1, int(args.workers))

            if workers == 1:
                for i, (label, payload) in enumerate(tests, 1):
                    print(f"[{i:03d}/{total}] {label[:50]}... ", end="", flush=True)
                    i, lbl, payload, payload_str, response_str = run_one(i, label, payload)
                    log(f, lbl, payload_str, response_str)
                    writer.writerow(
                        {
                            "run_ts": ts(),
                            "i": i,
                            "label": lbl,
                            "bank": (payload or {}).get("bank", ""),
                            "merchant_name": (payload or {}).get("merchant_name", ""),
                            "message": extract_message(response_str),
                        }
                    )
                    csv_f.flush()
            else:
                with ThreadPoolExecutor(max_workers=workers) as ex:
                    futures = [
                        ex.submit(run_one, i, label, payload)
                        for i, (label, payload) in enumerate(tests, 1)
                    ]
                    done = 0
                    for fut in as_completed(futures):
                        i, lbl, payload, payload_str, response_str = fut.result()
                        with lock:
                            done += 1
                            print(f"[{done:03d}/{total}] {lbl[:50]}... ", end="", flush=True)
                            log(f, lbl, payload_str, response_str)
                            writer.writerow(
                                {
                                    "run_ts": ts(),
                                    "i": i,
                                    "label": lbl,
                                    "bank": (payload or {}).get("bank", ""),
                                    "merchant_name": (payload or {}).get("merchant_name", ""),
                                    "message": extract_message(response_str),
                                }
                            )
                            csv_f.flush()
            f.write(f"\nRun completed : {ts()}\n")
        except KeyboardInterrupt:
            print("\n\nStopped with Ctrl+C. Partial results are in the log file.")
            f.write(f"\nRun interrupted : {ts()}\n")
            sys.exit(130)

    print(f"\nDone! Log written to: {os.path.abspath(LOG_FILE)}")
    print(f"Done! CSV written to: {os.path.abspath(out_csv_path)}")

if __name__ == "__main__":
    main()
