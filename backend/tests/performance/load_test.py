"""
Load testing script for library navigation endpoints.

This script simulates realistic user behavior:
1. Browse artists
2. Click on an artist to view works
3. Click on a work to view recordings
4. Apply filters to recordings
5. Navigate through pages

Usage:
    python -m tests.performance.load_test --users 10 --duration 60

Requirements:
    pip install aiohttp rich
"""

import asyncio
import time
from dataclasses import dataclass
from typing import List
import argparse
import random

try:
    import aiohttp
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, SpinnerColumn, TextColumn
except ImportError:
    # Don't exit during pytest collection - this is a standalone script
    import sys
    if "pytest" not in sys.modules:
        print("Please install required packages: pip install aiohttp rich")
        sys.exit(1)
    # During pytest collection, set these to None so the module can be imported
    aiohttp = None
    Console = None
    Table = None
    Progress = None
    SpinnerColumn = None
    TextColumn = None


@dataclass
class TestResult:
    """Result of a single request"""
    endpoint: str
    duration: float
    status_code: int
    cached: bool = False


class LoadTester:
    """Load tester for library navigation endpoints"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results: List[TestResult] = []
        self.console = Console()

    async def get_artist_ids(self, session: aiohttp.ClientSession) -> List[int]:
        """Get list of artist IDs from the library"""
        async with session.get(f"{self.base_url}/api/v1/library/artists") as resp:
            if resp.status == 200:
                artists = await resp.json()
                return [a["id"] for a in artists[:50]]  # Limit to 50 artists
        return []

    async def simulate_user_session(
        self,
        session: aiohttp.ClientSession,
        artist_ids: List[int],
        user_id: int
    ):
        """Simulate a single user browsing the library"""

        # Pick a random artist
        artist_id = random.choice(artist_ids)

        # 1. Get artist detail
        start = time.time()
        async with session.get(
            f"{self.base_url}/api/v1/library/artists/{artist_id}"
        ) as resp:
            duration = time.time() - start
            self.results.append(TestResult(
                endpoint=f"GET /artists/{artist_id}",
                duration=duration,
                status_code=resp.status
            ))

            if resp.status != 200:
                return

        # 2. Get artist's works
        start = time.time()
        async with session.get(
            f"{self.base_url}/api/v1/library/artists/{artist_id}/works",
            params={"limit": 24}
        ) as resp:
            duration = time.time() - start
            self.results.append(TestResult(
                endpoint=f"GET /artists/{artist_id}/works",
                duration=duration,
                status_code=resp.status
            ))

            if resp.status != 200:
                return

            works = await resp.json()
            if not works:
                return

            # Pick a random work
            work = random.choice(works)
            work_id = work["id"]

        # 3. Get work detail
        start = time.time()
        async with session.get(
            f"{self.base_url}/api/v1/library/works/{work_id}"
        ) as resp:
            duration = time.time() - start
            self.results.append(TestResult(
                endpoint=f"GET /works/{work_id}",
                duration=duration,
                status_code=resp.status
            ))

            if resp.status != 200:
                return

        # 4. Get work's recordings (no filter)
        start = time.time()
        async with session.get(
            f"{self.base_url}/api/v1/library/works/{work_id}/recordings",
            params={"limit": 100}
        ) as resp:
            duration = time.time() - start
            self.results.append(TestResult(
                endpoint=f"GET /works/{work_id}/recordings",
                duration=duration,
                status_code=resp.status
            ))

        # 5. Get work's recordings (with filters) - 50% of the time
        if random.random() < 0.5:
            status_filter = random.choice(["matched", "unmatched"])
            source_filter = random.choice(["library", "metadata"])

            start = time.time()
            async with session.get(
                f"{self.base_url}/api/v1/library/works/{work_id}/recordings",
                params={
                    "limit": 100,
                    "status": status_filter,
                    "source": source_filter
                }
            ) as resp:
                duration = time.time() - start
                self.results.append(TestResult(
                    endpoint=f"GET /works/{work_id}/recordings (filtered)",
                    duration=duration,
                    status_code=resp.status
                ))

        # Simulate user think time (1-3 seconds)
        await asyncio.sleep(random.uniform(1, 3))

    async def run_load_test(self, num_users: int, duration_seconds: int):
        """Run load test with specified number of concurrent users"""

        self.console.print(f"\n[bold cyan]Starting load test...[/bold cyan]")
        self.console.print(f"Users: {num_users}")
        self.console.print(f"Duration: {duration_seconds}s")
        self.console.print(f"Target: {self.base_url}\n")

        async with aiohttp.ClientSession() as session:
            # Get artist IDs
            self.console.print("[yellow]Fetching artist IDs...[/yellow]")
            artist_ids = await self.get_artist_ids(session)

            if not artist_ids:
                self.console.print("[red]No artists found! Please seed the database.[/red]")
                return

            self.console.print(f"[green]Found {len(artist_ids)} artists[/green]\n")

            # Run load test
            start_time = time.time()
            tasks = []

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console
            ) as progress:
                task = progress.add_task("Running load test...", total=None)

                while time.time() - start_time < duration_seconds:
                    # Maintain num_users concurrent sessions
                    while len(tasks) < num_users:
                        user_id = len(tasks)
                        task_obj = asyncio.create_task(
                            self.simulate_user_session(session, artist_ids, user_id)
                        )
                        tasks.append(task_obj)

                    # Wait for any task to complete
                    done, pending = await asyncio.wait(
                        tasks,
                        return_when=asyncio.FIRST_COMPLETED,
                        timeout=0.1
                    )

                    # Remove completed tasks
                    tasks = list(pending)

                # Wait for remaining tasks
                if tasks:
                    await asyncio.wait(tasks)

        # Print results
        self.print_results()

    def print_results(self):
        """Print test results in a formatted table"""

        if not self.results:
            self.console.print("[red]No results to display[/red]")
            return

        # Calculate statistics by endpoint
        endpoint_stats = {}
        for result in self.results:
            if result.endpoint not in endpoint_stats:
                endpoint_stats[result.endpoint] = {
                    "count": 0,
                    "total_time": 0,
                    "min_time": float('inf'),
                    "max_time": 0,
                    "errors": 0
                }

            stats = endpoint_stats[result.endpoint]
            stats["count"] += 1
            stats["total_time"] += result.duration
            stats["min_time"] = min(stats["min_time"], result.duration)
            stats["max_time"] = max(stats["max_time"], result.duration)

            if result.status_code >= 400:
                stats["errors"] += 1

        # Create results table
        table = Table(title="Load Test Results")
        table.add_column("Endpoint", style="cyan")
        table.add_column("Requests", justify="right", style="green")
        table.add_column("Avg (ms)", justify="right", style="yellow")
        table.add_column("Min (ms)", justify="right", style="blue")
        table.add_column("Max (ms)", justify="right", style="magenta")
        table.add_column("Errors", justify="right", style="red")
        table.add_column("Req/s", justify="right", style="green")

        total_requests = 0
        total_errors = 0
        total_time = sum(r.duration for r in self.results)

        for endpoint, stats in sorted(endpoint_stats.items()):
            avg_time = stats["total_time"] / stats["count"]
            req_per_sec = stats["count"] / total_time if total_time > 0 else 0

            table.add_row(
                endpoint,
                str(stats["count"]),
                f"{avg_time * 1000:.2f}",
                f"{stats['min_time'] * 1000:.2f}",
                f"{stats['max_time'] * 1000:.2f}",
                str(stats["errors"]),
                f"{req_per_sec:.2f}"
            )

            total_requests += stats["count"]
            total_errors += stats["errors"]

        self.console.print("\n")
        self.console.print(table)

        # Print summary
        self.console.print(f"\n[bold]Summary:[/bold]")
        self.console.print(f"Total Requests: {total_requests}")
        self.console.print(f"Total Errors: {total_errors}")
        self.console.print(f"Error Rate: {(total_errors / total_requests * 100):.2f}%")
        self.console.print(f"Total Duration: {total_time:.2f}s")
        self.console.print(f"Throughput: {total_requests / total_time:.2f} req/s")

        # Calculate percentiles
        all_durations = sorted([r.duration * 1000 for r in self.results])
        p50 = all_durations[len(all_durations) // 2]
        p95 = all_durations[int(len(all_durations) * 0.95)]
        p99 = all_durations[int(len(all_durations) * 0.99)]

        self.console.print(f"\n[bold]Response Time Percentiles:[/bold]")
        self.console.print(f"P50: {p50:.2f}ms")
        self.console.print(f"P95: {p95:.2f}ms")
        self.console.print(f"P99: {p99:.2f}ms")


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Load test library navigation endpoints")
    parser.add_argument(
        "--users",
        type=int,
        default=10,
        help="Number of concurrent users (default: 10)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Test duration in seconds (default: 60)"
    )
    parser.add_argument(
        "--url",
        type=str,
        default="http://localhost:8000",
        help="Base URL (default: http://localhost:8000)"
    )

    args = parser.parse_args()

    tester = LoadTester(base_url=args.url)
    await tester.run_load_test(args.users, args.duration)


if __name__ == "__main__":
    asyncio.run(main())

