"""
Predefined benchmark suite for M8 Baseline Comparison and Evaluation.
Contains 10 controlled benchmark tasks (B001 to B010) reproducing specific bug categories.
"""

from app.evaluation.models import BenchmarkCase


BENCHMARKS: dict[str, BenchmarkCase] = {
    "B001": BenchmarkCase(
        bug_id="B001",
        category="ZeroDivisionError",
        title="Division by Zero in Function Call",
        language="python",
        code="""def calculate(x):
    return 10 / x

def process():
    value = 0
    return calculate(value)

process()""",
        stdin="",
        expected_error="ZeroDivisionError",
        description="A nested function performs arithmetic division where the divisor argument evaluates to zero at runtime.",
        expected_root_cause="The caller process() initializes value to 0 and passes it into calculate(), where it is used directly as the divisor in 10 / x without validation.",
        expected_behavior="process() should provide a non-zero divisor (or calculate() should handle a zero divisor safely) so that 10 / x computes a valid numeric quotient without raising ZeroDivisionError."
    ),
    "B002": BenchmarkCase(
        bug_id="B002",
        category="IndexError",
        title="Rank Index Calculation Exceeds Bounds",
        language="python",
        code="""def compute_rank_index(players, rank):
    return rank

def get_ranked_player(players, rank_idx):
    return players[rank_idx]

def evaluate_leaderboard():
    leaderboard = ["Alice", "Bob", "Charlie"]
    idx = compute_rank_index(leaderboard, 3)
    return get_ranked_player(leaderboard, idx)

evaluate_leaderboard()""",
        stdin="",
        expected_error="IndexError",
        description="1-based rank computation directly indexes a 0-based list, resulting in an out-of-range index lookup on the final rank.",
        expected_root_cause="compute_rank_index() returns the 1-based rank value (3) without converting it to a 0-based index (rank - 1), causing get_ranked_player() to access index 3 on a 3-element list with valid indices 0 to 2.",
        expected_behavior="compute_rank_index() should convert 1-based rank to 0-based index (rank - 1), allowing get_ranked_player() to access leaderboard[2] and return 'Charlie'."
    ),
    "B003": BenchmarkCase(
        bug_id="B003",
        category="KeyError",
        title="Missing Authentication Header Key",
        language="python",
        code="""def extract_header(headers, header_name):
    return headers[header_name]

def authenticate_session(request_data):
    headers = request_data.get("headers", {})
    token = extract_header(headers, "authorization")
    return f"Bearer {token}"

def handle_incoming_request():
    request = {
        "endpoint": "/api/v1/resource",
        "headers": {
            "content-type": "application/json",
            "auth_token": "secret_abc123"
        }
    }
    return authenticate_session(request)

handle_incoming_request()""",
        stdin="",
        expected_error="KeyError",
        description="Authentication handler attempts direct dictionary access for 'authorization' key when client header was supplied as 'auth_token'.",
        expected_root_cause="authenticate_session() attempts to retrieve key 'authorization' from the headers dictionary, but the client request payload was provided with key 'auth_token', causing extract_header() to raise KeyError.",
        expected_behavior="The header lookup should access 'auth_token' (or handle missing headers gracefully), returning 'Bearer secret_abc123'."
    ),
    "B004": BenchmarkCase(
        bug_id="B004",
        category="TypeError",
        title="String and Float Arithmetic Mismatch Across Calls",
        language="python",
        code="""def parse_configuration(raw_config):
    return {
        "service": raw_config.get("name"),
        "timeout": raw_config.get("timeout_sec", "30")
    }

def calculate_deadline(base_time, timeout):
    return base_time + timeout

def schedule_job():
    config = parse_configuration({"name": "worker", "timeout_sec": "45"})
    start_time = 100.0
    deadline = calculate_deadline(start_time, config["timeout"])
    return deadline

schedule_job()""",
        stdin="",
        expected_error="TypeError",
        description="Configuration parser propagates timeout as a string rather than a numeric value, causing a TypeError when added to a float timestamp.",
        expected_root_cause="parse_configuration() keeps 'timeout_sec' as string '45' instead of casting it to float or int, causing calculate_deadline() to attempt arithmetic addition between float 100.0 and string '45'.",
        expected_behavior="The timeout value should be cast to a numeric type (float or int), allowing calculate_deadline() to perform addition and return 145.0."
    ),
    "B005": BenchmarkCase(
        bug_id="B005",
        category="ValueError",
        title="Invalid Literal in Transaction Segment Parsing",
        language="python",
        code="""def extract_numeric_code(code_str):
    return int(code_str)

def parse_transaction(raw_tx):
    parts = raw_tx.split(":")
    tag = parts[0]
    tx_code = parts[1]
    return extract_numeric_code(tx_code)

def execute_transaction():
    tx_data = "TX:TRANSFER_99:250"
    return parse_transaction(tx_data)

execute_transaction()""",
        stdin="",
        expected_error="ValueError",
        description="Transaction parser indexes an alphanumeric identifier segment instead of the numeric amount segment when converting to integer.",
        expected_root_cause="parse_transaction() extracts parts[1] ('TRANSFER_99', the transaction label) instead of parts[2] ('250', the numeric amount) and passes it to extract_numeric_code(), where int() fails on non-digit characters.",
        expected_behavior="parse_transaction() should extract the numeric amount segment (parts[2]) so extract_numeric_code() successfully returns integer 250."
    ),
    "B006": BenchmarkCase(
        bug_id="B006",
        category="Logic error",
        title="Accidental Reset in Discount Accumulator Loop",
        language="python",
        code="""def calculate_total_discount(prices, discount_rate):
    total_discount = 0.0
    for price in prices:
        discount = price * discount_rate
        total_discount = discount
    return total_discount

def run_cart():
    items = [100.0, 200.0, 50.0]
    rate = 0.10
    result = calculate_total_discount(items, rate)
    print(f"Total discount: {result}")
    return result

run_cart()""",
        stdin="",
        expected_error="LogicError (Incorrect Output)",
        description="Loop execution reassigns the accumulator variable instead of adding to it, causing only the last iteration's discount to be returned.",
        expected_root_cause="The accumulator total_discount is overwritten inside the loop (total_discount = discount) rather than accumulated (total_discount += discount), causing the function to discard previous item discounts and return only the final iteration's value (5.0 instead of 35.0).",
        expected_behavior="The loop should accumulate discounts across all items (total_discount += discount), producing a total discount of 35.0 across the three items [100.0, 200.0, 50.0] at a 10% rate."
    ),
    "B007": BenchmarkCase(
        bug_id="B007",
        category="State/mutation bug",
        title="Mutable Default Argument Permission Leak",
        language="python",
        code="""def create_user_session(user_id, permissions=[]):
    permissions.append("read")
    return {"user_id": user_id, "permissions": permissions}

def grant_admin(session):
    session["permissions"].append("admin")
    return session

def run_security_pipeline():
    user1 = create_user_session("alice")
    grant_admin(user1)
    user2 = create_user_session("bob")
    assert "admin" not in user2["permissions"], f"Security violation: {user2['user_id']} leaked admin permission"
    return user2

run_security_pipeline()""",
        stdin="",
        expected_error="AssertionError",
        description="A function uses a mutable list as a default parameter, causing state modifications from earlier calls to contaminate subsequent user sessions.",
        expected_root_cause="create_user_session() defines a mutable default argument (permissions=[]), which is evaluated once at definition time and shared across calls. When alice is granted 'admin', the shared list is mutated, causing bob's new session to inherit alice's admin permission and trigger an AssertionError.",
        expected_behavior="create_user_session() should use permissions=None and initialize a new list inside the function (permissions = [] if permissions is None else permissions), ensuring user sessions do not share mutable state and bob is not granted admin."
    ),
    "B008": BenchmarkCase(
        bug_id="B008",
        category="Class/OOP bug",
        title="Incompatible None State in Order Cancellation",
        language="python",
        code="""class OrderManager:
    def __init__(self, order_id: str):
        self.order_id = order_id
        self.status = "pending"
        self.items = {}

    def add_item(self, item_name: str, quantity: int):
        self.items[item_name] = quantity

    def cancel_order(self):
        self.status = "cancelled"
        self.items = None

    def get_total_items(self):
        return sum(self.items.values())

def process_cancellation():
    manager = OrderManager("ORD-501")
    manager.add_item("keyboard", 1)
    manager.add_item("mouse", 2)
    manager.cancel_order()
    return manager.get_total_items()

process_cancellation()""",
        stdin="",
        expected_error="AttributeError",
        description="An order management class resets an instance attribute dictionary to None upon cancellation, breaking subsequent method calls expecting a collection.",
        expected_root_cause="cancel_order() resets self.items to None instead of clearing the dictionary (self.items.clear() or self.items = {}), causing get_total_items() to raise an AttributeError when attempting to call .values() on NoneType.",
        expected_behavior="cancel_order() should reset self.items to an empty dictionary or clear it, so get_total_items() safely computes a sum of 0 items without an AttributeError."
    ),
    "B009": BenchmarkCase(
        bug_id="B009",
        category="Inheritance/polymorphism bug",
        title="Case-Sensitive Lookup in Overridden Polymorphic Method",
        language="python",
        code="""class BaseAccount:
    def __init__(self, account_holder: str, initial_balance: float):
        self.account_holder = account_holder
        self.balance = initial_balance

    def calculate_interest(self) -> float:
        return self.balance * 0.01

    def apply_annual_charge(self) -> float:
        interest = self.calculate_interest()
        self.balance += interest
        return self.balance

class PremiumAccount(BaseAccount):
    def __init__(self, account_holder: str, initial_balance: float, tier: str):
        super().__init__(account_holder, initial_balance)
        self.tier = tier

    def calculate_interest(self) -> float:
        tier_multipliers = {"gold": 0.05, "platinum": 0.08}
        multiplier = tier_multipliers[self.tier]
        return self.balance * multiplier

def run_accounting():
    account = PremiumAccount("Dr. Smith", 10000.0, "Gold")
    return account.apply_annual_charge()

run_accounting()""",
        stdin="",
        expected_error="KeyError",
        description="A derived class overrides a base calculation method called polymorphically by a base method, but performs a case-sensitive dictionary lookup against unnormalized instance state.",
        expected_root_cause="PremiumAccount.calculate_interest() overrides BaseAccount.calculate_interest() and attempts a direct dictionary lookup tier_multipliers[self.tier] without normalizing the string, raising KeyError: 'Gold' because the dictionary keys are lowercase ('gold', 'platinum').",
        expected_behavior="PremiumAccount.calculate_interest() should normalize self.tier using .lower(), allowing tier_multipliers['gold'] to resolve to 0.05 and returning an updated balance of 10500.0."
    ),
    "B010": BenchmarkCase(
        bug_id="B010",
        category="Multi-function / deeper call-chain bug",
        title="Multi-Frame Buffer Offset Boundary Overshoot",
        language="python",
        code="""def read_chunk_byte(buffer, offset):
    return buffer[offset]

def unpack_header_field(data_bytes, start_pos, length):
    end_pos = start_pos + length
    return read_chunk_byte(data_bytes, end_pos)

def parse_packet_metadata(raw_packet):
    header = raw_packet.get("header_bytes", b"")
    field_length = 8
    return unpack_header_field(header, 0, field_length)

def route_network_packet():
    packet = {
        "packet_id": 1001,
        "header_bytes": b"PKT_HEAD"
    }
    return parse_packet_metadata(packet)

route_network_packet()""",
        stdin="",
        expected_error="IndexError",
        description="A call chain of 4 functions passes an off-by-one computed boundary down to a low-level buffer reader, triggering an out-of-bounds index error several frames deep.",
        expected_root_cause="unpack_header_field() computes end_pos = start_pos + length (8) and passes it as a single-byte index to read_chunk_byte(), which attempts to access buffer[8] on an 8-byte buffer whose valid 0-based indices are 0 to 7.",
        expected_behavior="unpack_header_field() should pass start_pos (or slice data_bytes[start_pos:end_pos]) rather than end_pos to read_chunk_byte(), avoiding the out-of-range IndexError and returning the packet header."
    ),
}


def get_all_benchmarks() -> list[BenchmarkCase]:
    """Return all predefined benchmark cases in order."""
    return list(BENCHMARKS.values())


def get_benchmark(bug_id: str) -> BenchmarkCase | None:
    """Retrieve benchmark case by ID (case-insensitive)."""
    return BENCHMARKS.get(bug_id.strip().upper())
