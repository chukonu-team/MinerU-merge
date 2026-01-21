#!/usr/bin/env python3
"""
Generate flame graph from Nsight Systems sqlite database
"""
import sqlite3
import subprocess
from collections import defaultdict

DB_PATH = "/data/MinerU/report_cuda.sqlite"
OUTPUT_FOLDED = "/tmp/cuda_stacks_folded.txt"
OUTPUT_SVG = "/data/MinerU/cuda_flamegraph.svg"

def get_string_name(conn, string_id):
    """Get string value from StringIds table"""
    cursor = conn.execute("SELECT value FROM StringIds WHERE id = ?", (string_id,))
    row = cursor.fetchone()
    return row[0] if row else f"unknown_{string_id}"

def generate_flamegraph_data():
    """Extract API call stacks and generate folded format for flamegraph"""
    conn = sqlite3.connect(DB_PATH)

    # Query OSRT_API for API calls with timing and names
    query = """
    SELECT
        oa.start,
        oa.end,
        oa.nestingLevel,
        s.value as function_name,
        oa.globalTid
    FROM OSRT_API oa
    JOIN StringIds s ON oa.nameId = s.id
    WHERE oa.end > oa.start
    ORDER BY oa.globalTid, oa.start, oa.nestingLevel
    """

    cursor = conn.execute(query)
    stacks = defaultdict(int)

    # Build call stacks from API calls
    # For each API call, we create a stack trace based on nesting
    call_stack = {}  # Track stack per thread

    for row in cursor:
        start, end, nesting, func_name, tid = row
        duration = end - start

        # Simple stack based on function name
        # For a more accurate flame graph, we'd need to reconstruct the full call chain
        stack_key = f"{func_name}"
        stacks[stack_key] += duration

    conn.close()

    # Write folded stack format
    with open(OUTPUT_FOLDED, 'w') as f:
        for stack, count in sorted(stacks.items(), key=lambda x: -x[1]):
            f.write(f"{stack} {count}\n")

    print(f"Generated folded stack data: {OUTPUT_FOLDED}")
    print(f"Total unique functions: {len(stacks)}")

def generate_svg():
    """Generate SVG flamegraph from folded data"""
    cmd = [
        "/opt/FlameGraph/flamegraph.pl",
        "--title", "CUDA API Flame Graph",
        "--countname", "nanoseconds",
        "--nametype", "API",
        OUTPUT_FOLDED
    ]

    with open(OUTPUT_SVG, 'w') as f:
        subprocess.run(cmd, stdout=f, check=True)

    print(f"Generated flamegraph SVG: {OUTPUT_SVG}")

def get_top_functions():
    """Display top functions by execution time"""
    conn = sqlite3.connect(DB_PATH)

    query = """
    SELECT
        s.value as function_name,
        COUNT(*) as call_count,
        SUM(oa.end - oa.start) as total_time_ns,
        AVG(oa.end - oa.start) as avg_time_ns
    FROM OSRT_API oa
    JOIN StringIds s ON oa.nameId = s.id
    WHERE oa.end > oa.start
    GROUP BY s.value
    ORDER BY total_time_ns DESC
    LIMIT 30
    """

    print("\n=== Top 30 Functions by Total Time ===")
    print(f"{'Function':<50} {'Calls':>10} {'Total (ms)':>12} {'Avg (us)':>12}")
    print("-" * 86)

    cursor = conn.execute(query)
    for row in cursor:
        func_name, call_count, total_ns, avg_ns = row
        total_ms = total_ns / 1_000_000
        avg_us = avg_ns / 1_000
        func_display = func_name[:47] + "..." if len(func_name) > 50 else func_name
        print(f"{func_display:<50} {call_count:>10} {total_ms:>12.2f} {avg_us:>12.2f}")

    conn.close()

if __name__ == "__main__":
    print("Extracting performance data from Nsight Systems database...")
    get_top_functions()
    print("\nGenerating flame graph...")
    generate_flamegraph_data()
    generate_svg()
    print(f"\n✅ Flame graph saved to: {OUTPUT_SVG}")
    print("You can open this SVG file in a web browser to view the interactive flame graph.")
