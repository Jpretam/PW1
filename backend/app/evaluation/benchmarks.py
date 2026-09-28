"""
Predefined benchmark suite for M8 Baseline Comparison and Evaluation.
Contains 8 controlled benchmark tasks (B001 to B008) reproducing specific bug categories.
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
        description="A nested function performs arithmetic division where the divisor argument evaluates to zero at runtime."
    ),
    "B002": BenchmarkCase(
        bug_id="B002",
        category="IndexError",
        title="List Index Out of Range",
        language="python",
        code="""def get_element(items, index):
    return items[index]

def run():
    numbers = [10, 20, 30]
    return get_element(numbers, 3)

run()""",
        stdin="",
        expected_error="IndexError",
        description="Direct retrieval from a 3-element list at index 3 exceeds list bounds."
    ),
    "B003": BenchmarkCase(
        bug_id="B003",
        category="incorrect variable/state",
        title="Unbound Local Variable in Conditional",
        language="python",
        code="""def calculate_discount(price):
    if price > 100:
        discount = 15
    return price - discount

print(calculate_discount(50))""",
        stdin="",
        expected_error="UnboundLocalError",
        description="Local variable 'discount' is referenced in the return statement without being assigned in the else branch."
    ),
    "B004": BenchmarkCase(
        bug_id="B004",
        category="boundary/off-by-one",
        title="Off-by-One Loop Boundary Index",
        language="python",
        code="""def sum_elements(arr):
    total = 0
    for i in range(len(arr) + 1):
        total += arr[i]
    return total

sum_elements([1, 2, 3, 4])""",
        stdin="",
        expected_error="IndexError",
        description="Loop upper bound uses len(arr) + 1, causing an out-of-bounds index access on the final iteration."
    ),
    "B005": BenchmarkCase(
        bug_id="B005",
        category="incorrect function argument",
        title="Missing Required Positional Argument",
        language="python",
        code="""def format_user(name, age, city):
    return f"{name}, {age} from {city}"

def main():
    return format_user("Alice", 30)

main()""",
        stdin="",
        expected_error="TypeError",
        description="Function call omits the required 'city' argument, causing a TypeError."
    ),
    "B006": BenchmarkCase(
        bug_id="B006",
        category="conditional/logic error",
        title="Inverted Authorization Check",
        language="python",
        code="""def check_access(user_role):
    if user_role == "admin":
        is_allowed = False
    else:
        is_allowed = True
    assert is_allowed, "Access denied: user role is not authorized"

check_access("admin")""",
        stdin="",
        expected_error="AssertionError",
        description="Authorization condition incorrectly sets is_allowed to False for admin, triggering an AssertionError."
    ),
    "B007": BenchmarkCase(
        bug_id="B007",
        category="loop-related error",
        title="Division by Element After List Mutation",
        language="python",
        code="""def process_queue(items):
    total = 100
    for item in items:
        result = total / item
        print(f"Result: {result}")

process_queue([10, 20, 0, 40])""",
        stdin="",
        expected_error="ZeroDivisionError",
        description="Iterating through a numeric batch encounters an unvalidated zero element causing a mid-loop division failure."
    ),
    "B008": BenchmarkCase(
        bug_id="B008",
        category="call-stack/state error",
        title="Multi-Frame Missing Dictionary Key",
        language="python",
        code="""def parse_token(data):
    return int(data["auth_token"])

def handle_request(payload):
    return parse_token(payload)

def authenticate():
    user_payload = {"user_id": 42}
    return handle_request(user_payload)

authenticate()""",
        stdin="",
        expected_error="KeyError",
        description="Nested three-frame call stack attempts to access non-existent dictionary key 'auth_token'."
    ),
}


def get_all_benchmarks() -> list[BenchmarkCase]:
    """Return all predefined benchmark cases in order."""
    return list(BENCHMARKS.values())


def get_benchmark(bug_id: str) -> BenchmarkCase | None:
    """Retrieve benchmark case by ID (case-insensitive)."""
    return BENCHMARKS.get(bug_id.strip().upper())
