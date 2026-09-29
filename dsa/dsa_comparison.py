"""Compare linear search with dictionary lookup on the SMS transactions.

Run it with:
    python dsa/dsa_comparison.py

Both ways find a transaction by its id. The list has to check the records
one at a time, while the dictionary goes straight to the answer.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dsa.parse_sms import index_by_id, load_transactions

RUNS = int(sys.argv[1]) if len(sys.argv) > 1 else 100000


def linear_search(records, wanted_id):
    """Go through the list until the id is found. O(n)."""
    for record in records:
        if record["id"] == wanted_id:
            return record
    return None


def dict_lookup(records_by_id, wanted_id):
    """Ask the dictionary for the id. O(1)."""
    return records_by_id.get(wanted_id)


def time_search(function, records, wanted_id, runs=RUNS):
    """Run the search many times and return the average time in microseconds."""
    start = time.perf_counter()
    for _ in range(runs):
        function(records, wanted_id)
    seconds = time.perf_counter() - start
    return seconds / runs * 1000000


def main():
    records = load_transactions()
    records_by_id = index_by_id(records)
    ids = [record["id"] for record in records]

    cases = [
        ("first record", ids[0]),
        ("middle record", ids[len(ids) // 2]),
        ("last record", ids[-1]),
        ("id not in the data", max(ids) + 999),
    ]

    print(f"{len(records)} transactions, {RUNS:,} searches per case\n")
    print("Case                  Linear search    Dictionary     Faster by")
    print("-" * 63)
    for name, wanted_id in cases:
        list_time = time_search(linear_search, records, wanted_id)
        dict_time = time_search(dict_lookup, records_by_id, wanted_id)
        print(f"{name:<22}{list_time:>9.3f} µs{dict_time:>12.3f} µs{list_time / dict_time:>12.1f}x")
    print("-" * 63)

    # what happens when there is more data: the same records copied over and
    # over with new ids, always looking for the last one
    print("\nWith more records (looking for the last one):\n")
    print("  Records     Linear search      Dictionary     Faster by")
    print("-" * 57)
    for copies in [1, 10, 100, 1000]:
        bigger = []
        for number, record in enumerate(records * copies, start=1):
            copy = dict(record)
            copy["id"] = number
            bigger.append(copy)
        bigger_by_id = index_by_id(bigger)
        wanted_id = len(bigger)
        runs = max(RUNS // copies, 200)

        list_time = time_search(linear_search, bigger, wanted_id, runs)
        dict_time = time_search(dict_lookup, bigger_by_id, wanted_id, runs)
        print(f"{len(bigger):>9,}{list_time:>13.2f} µs{dict_time:>12.3f} µs{list_time / dict_time:>12,.0f}x")
    print("-" * 57)

    print("""
Why the dictionary is faster

    Linear search checks the records one after another, so the more
    records there are, the longer it takes. That is O(n): ten times the
    records, ten times the work, which is what the second table shows.
    It is slowest when the id is the last one or is not there at all,
    because then it has to check everything.

    A dictionary turns the id into a hash, and the hash says exactly
    where the record is kept, so it does not look at the other records
    at all. That is O(1): the time stays the same no matter how many
    records there are. This is why the API keeps the transactions in a
    dictionary instead of a list.

Another way to search

    If the list is sorted by id, binary search (the bisect module) cuts
    the list in half each time, which is O(log n): about 15 steps for
    25,000 records instead of 25,000. It is slower than the dictionary
    for finding one id, but it keeps the records in order, so it can
    also answer questions like "all transactions between these dates".
    A database index works this way.
""")


if __name__ == "__main__":
    main()
