#!/usr/bin/env python3
"""
Generate detailed performance analysis from Nsight Systems data
"""
import sqlite3
import json
from collections import defaultdict

DB_PATH = "/data/MinerU/report_cuda.sqlite"
OUTPUT_HTML = "/data/MinerU/cuda_analysis.html"

def get_timeline_data(conn):
    """Get timeline data for visualization"""
    query = """
    SELECT
        start,
        end,
        s.value as function_name,
        globalTid
    FROM OSRT_API oa
    JOIN StringIds s ON oa.nameId = s.id
    WHERE oa.end > oa.start
    ORDER BY start
    LIMIT 5000
    """
    cursor = conn.execute(query)
    events = []
    for row in cursor:
        start, end, func_name, tid = row
        events.append({
            'start': start,
            'end': end,
            'duration': end - start,
            'name': func_name,
            'tid': tid
        })
    return events

def get_thread_summary(conn):
    """Get per-thread execution summary"""
    query = """
    SELECT
        globalTid,
        COUNT(*) as call_count,
        SUM(end - start) as total_time_ns
    FROM OSRT_API
    WHERE end > start
    GROUP BY globalTid
    ORDER BY total_time_ns DESC
    """
    cursor = conn.execute(query)
    threads = []
    for row in cursor:
        tid, count, total_ns = row
        threads.append({
            'tid': tid,
            'calls': count,
            'total_ms': total_ns / 1_000_000
        })
    return threads

def generate_html_report():
    """Generate comprehensive HTML report"""
    conn = sqlite3.connect(DB_PATH)

    # Get data
    events = get_timeline_data(conn)
    threads = get_thread_summary(conn)

    # Get function breakdown
    query = """
    SELECT
        s.value,
        COUNT(*) as call_count,
        SUM(oa.end - oa.start) as total_time,
        MIN(oa.end - oa.start) as min_time,
        MAX(oa.end - oa.start) as max_time,
        AVG(oa.end - oa.start) as avg_time
    FROM OSRT_API oa
    JOIN StringIds s ON oa.nameId = s.id
    WHERE oa.end > oa.start
    GROUP BY s.value
    ORDER BY total_time DESC
    LIMIT 50
    """
    cursor = conn.execute(query)
    functions = []
    for row in cursor:
        name, count, total, min_t, max_t, avg_t = row
        functions.append({
            'name': name,
            'calls': count,
            'total_ms': total / 1_000_000,
            'min_us': min_t / 1_000,
            'max_us': max_t / 1_000,
            'avg_us': avg_t / 1_000
        })

    conn.close()

    # Calculate totals
    total_events = len(events)
    total_time_ns = max(e['end'] for e in events) - min(e['start'] for e in events) if events else 0
    total_time_ms = total_time_ns / 1_000_000

    # Generate HTML
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>CUDA Performance Analysis</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #1a1a2e; color: #eee; }}
        h1 {{ color: #4fc3f7; border-bottom: 2px solid #4fc3f7; padding-bottom: 10px; }}
        h2 {{ color: #81c784; margin-top: 30px; }}
        .summary {{ background: #16213e; padding: 15px; border-radius: 8px; margin: 20px 0; }}
        .metric {{ display: inline-block; margin: 10px 20px; }}
        .metric-value {{ font-size: 24px; font-weight: bold; color: #4fc3f7; }}
        .metric-label {{ font-size: 14px; color: #aaa; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th {{ background: #0f3460; color: #4fc3f7; padding: 12px; text-align: left; position: sticky; top: 0; }}
        td {{ padding: 10px; border-bottom: 1px solid #333; }}
        tr:hover {{ background: #1a1a2e; }}
        .bar-container {{ display: flex; align-items: center; }}
        .bar {{ height: 20px; background: linear-gradient(90deg, #4fc3f7, #81c784); border-radius: 3px; }}
        .bar-label {{ margin-left: 10px; font-size: 12px; color: #aaa; }}
        .section {{ background: #16213e; padding: 20px; border-radius: 8px; margin: 20px 0; }}
    </style>
</head>
<body>
    <h1>🔥 CUDA Performance Analysis Report</h1>

    <div class="summary">
        <div class="metric">
            <div class="metric-value">{total_time_ms:.2f} ms</div>
            <div class="metric-label">Total Execution Time</div>
        </div>
        <div class="metric">
            <div class="metric-value">{len(functions)}</div>
            <div class="metric-label">Unique Functions</div>
        </div>
        <div class="metric">
            <div class="metric-value">{sum(f['calls'] for f in functions):,}</div>
            <div class="metric-label">Total API Calls</div>
        </div>
        <div class="metric">
            <div class="metric-value">{len(threads)}</div>
            <div class="metric-label">Active Threads</div>
        </div>
    </div>

    <div class="section">
        <h2>📊 Top Functions by Total Time</h2>
        <table>
            <thead>
                <tr>
                    <th>Function</th>
                    <th>Calls</th>
                    <th>Total (ms)</th>
                    <th>Avg (μs)</th>
                    <th>Min (μs)</th>
                    <th>Max (μs)</th>
                    <th>Visualization</th>
                </tr>
            </thead>
            <tbody>
"""

    max_time = functions[0]['total_ms'] if functions else 1

    for func in functions:
        bar_width = (func['total_ms'] / max_time) * 100
        html += f"""
                <tr>
                    <td title="{func['name']}">{func['name'][:60]}</td>
                    <td>{func['calls']:,}</td>
                    <td>{func['total_ms']:.2f}</td>
                    <td>{func['avg_us']:.2f}</td>
                    <td>{func['min_us']:.2f}</td>
                    <td>{func['max_us']:.2f}</td>
                    <td>
                        <div class="bar-container">
                            <div class="bar" style="width: {bar_width}%"></div>
                            <span class="bar-label">{bar_width:.1f}%</span>
                        </div>
                    </td>
                </tr>
"""

    html += """
            </tbody>
        </table>
    </div>

    <div class="section">
        <h2>🧵 Thread Activity</h2>
        <table>
            <thead>
                <tr>
                    <th>Thread ID</th>
                    <th>API Calls</th>
                    <th>Total Time (ms)</th>
                </tr>
            </thead>
            <tbody>
"""

    for thread in threads[:20]:  # Top 20 threads
        html += f"""
                <tr>
                    <td>{thread['tid']}</td>
                    <td>{thread['calls']:,}</td>
                    <td>{thread['total_ms']:.2f}</td>
                </tr>
"""

    html += """
            </tbody>
        </table>
    </div>

    <div class="section">
        <h2>💡 Key Insights</h2>
        <ul>
"""

    # Add insights
    if functions:
        top_func = functions[0]
        html += f"<li><strong>Highest Impact:</strong> {top_func['name']} accounts for {top_func['total_ms']:.2f}ms ({top_func['total_ms']/total_time_ms*100:.1f}% of total time)</li>"

        slow_functions = [f for f in functions if f['avg_us'] > 1000]
        if slow_functions:
            html += f"<li><strong>Slow Functions:</strong> {len(slow_functions)} functions have average execution time > 1ms</li>"

        frequent_functions = [f for f in functions if f['calls'] > 10000]
        if frequent_functions:
            html += f"<li><strong>Frequent Calls:</strong> {len(frequent_functions)} functions called more than 10,000 times</li>"

    html += """
        </ul>
    </div>
</body>
</html>
"""

    with open(OUTPUT_HTML, 'w') as f:
        f.write(html)

    print(f"Generated HTML report: {OUTPUT_HTML}")

if __name__ == "__main__":
    generate_html_report()
    print("✅ Analysis complete!")
