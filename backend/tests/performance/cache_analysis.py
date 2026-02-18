"""
Cache hit rate analysis script.

This script measures cache effectiveness by:
1. Making requests to endpoints
2. Tracking cache hits vs misses
3. Calculating hit rates
4. Providing recommendations

Usage:
    python -m tests.performance.cache_analysis --requests 100

Requirements:
    pip install aiohttp rich
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Dict, List
import argparse
import random

try:
    import aiohttp
    from rich.console import Console
    from rich.table import Table
    from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
except ImportError:
    print("Please install required packages: pip install aiohttp rich")
    exit(1)


@dataclass
class CacheMetric:
    """Cache metrics for an endpoint"""
    endpoint: str
    total_requests: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    avg_hit_time: float = 0
    avg_miss_time: float = 0
    hit_times: List[float] = None
    miss_times: List[float] = None

    def __post_init__(self):
        if self.hit_times is None:
            self.hit_times = []
        if self.miss_times is None:
            self.miss_times = []

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate as percentage"""
        if self.total_requests == 0:
            return 0.0
        return (self.cache_hits / self.total_requests) * 100

    def add_request(self, duration: float, is_hit: bool):
        """Add a request to the metrics"""
        self.total_requests += 1
        if is_hit:
            self.cache_hits += 1
            self.hit_times.append(duration)
        else:
            self.cache_misses += 1
            self.miss_times.append(duration)

        # Update averages
        if self.hit_times:
            self.avg_hit_time = sum(self.hit_times) / len(self.hit_times)
        if self.miss_times:
            self.avg_miss_time = sum(self.miss_times) / len(self.miss_times)


class CacheAnalyzer:
    """Analyze cache performance"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.metrics: Dict[str, CacheMetric] = {}
        self.console = Console()

    async def get_artist_ids(self, session: aiohttp.ClientSession) -> List[int]:
        """Get list of artist IDs"""
        async with session.get(f"{self.base_url}/api/v1/library/artists") as resp:
            if resp.status == 200:
                artists = await resp.json()
                return [a["id"] for a in artists[:20]]  # Limit to 20 artists
        return []

    async def test_endpoint(
        self,
        session: aiohttp.ClientSession,
        endpoint_name: str,
        url: str,
        params: dict = None
    ):
        """Test a single endpoint and measure cache performance"""

        if endpoint_name not in self.metrics:
            self.metrics[endpoint_name] = CacheMetric(endpoint=endpoint_name)

        # First request (cache miss)
        start = time.time()
        async with session.get(url, params=params) as resp:
            first_duration = time.time() - start
            if resp.status != 200:
                return

        self.metrics[endpoint_name].add_request(first_duration, is_hit=False)

        # Second request (should be cache hit)
        await asyncio.sleep(0.1)  # Small delay
        start = time.time()
        async with session.get(url, params=params) as resp:
            second_duration = time.time() - start
            if resp.status != 200:
                return

        # If second request is significantly faster, it's a cache hit
        is_hit = second_duration < (first_duration * 0.5)
        self.metrics[endpoint_name].add_request(second_duration, is_hit=is_hit)

    async def run_analysis(self, num_requests: int):
        """Run cache analysis"""

        self.console.print(f"\n[bold cyan]Starting cache analysis...[/bold cyan]")
        self.console.print(f"Requests per endpoint: {num_requests}")
        self.console.print(f"Target: {self.base_url}\n")

        async with aiohttp.ClientSession() as session:
            # Get artist IDs
            self.console.print("[yellow]Fetching artist IDs...[/yellow]")
            artist_ids = await self.get_artist_ids(session)

            if not artist_ids:
                self.console.print("[red]No artists found! Please seed the database.[/red]")
                return

            self.console.print(f"[green]Found {len(artist_ids)} artists[/green]\n")

            # Test endpoints
            with Progress(
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeRemainingColumn(),
                console=self.console


    def print_results(self):
        """Print cache analysis results"""

        if not self.metrics:
            self.console.print("[red]No metrics to display[/red]")
            return

        # Create results table
        table = Table(title="Cache Performance Analysis")
        table.add_column("Endpoint", style="cyan")
        table.add_column("Requests", justify="right", style="green")
        table.add_column("Hit Rate", justify="right", style="yellow")
        table.add_column("Avg Hit (ms)", justify="right", style="blue")
        table.add_column("Avg Miss (ms)", justify="right", style="magenta")
        table.add_column("Speedup", justify="right", style="green")

        for endpoint, metric in sorted(self.metrics.items()):
            speedup = (
                metric.avg_miss_time / metric.avg_hit_time
                if metric.avg_hit_time > 0
                else 0
            )

            table.add_row(
                endpoint,
                str(metric.total_requests),
                f"{metric.hit_rate:.1f}%",
                f"{metric.avg_hit_time * 1000:.2f}",
                f"{metric.avg_miss_time * 1000:.2f}",
                f"{speedup:.1f}x"
            )

        self.console.print("\n")
        self.console.print(table)

        # Print recommendations
        self.console.print(f"\n[bold]Recommendations:[/bold]")

        for endpoint, metric in self.metrics.items():
            if metric.hit_rate < 50:
                self.console.print(
                    f"[yellow]⚠ {endpoint}: Low hit rate ({metric.hit_rate:.1f}%). "
                    f"Consider increasing TTL.[/yellow]"
                )
            elif metric.hit_rate > 90:
                self.console.print(
                    f"[green]✓ {endpoint}: Excellent hit rate ({metric.hit_rate:.1f}%)[/green]"
                )
            else:
                self.console.print(
                    f"[blue]ℹ {endpoint}: Good hit rate ({metric.hit_rate:.1f}%)[/blue]"
                )

        # Overall statistics
        total_requests = sum(m.total_requests for m in self.metrics.values())
        total_hits = sum(m.cache_hits for m in self.metrics.values())
        overall_hit_rate = (total_hits / total_requests * 100) if total_requests > 0 else 0

        self.console.print(f"\n[bold]Overall Statistics:[/bold]")
        self.console.print(f"Total Requests: {total_requests}")
        self.console.print(f"Total Cache Hits: {total_hits}")
        self.console.print(f"Overall Hit Rate: {overall_hit_rate:.1f}%")


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Analyze cache performance")
    parser.add_argument(
        "--requests",
        type=int,
        default=50,
        help="Number of requests per endpoint (default: 50)"
    )
    parser.add_argument(
        "--url",
        type=str,
        default="http://localhost:8000",
        help="Base URL (default: http://localhost:8000)"
    )

    args = parser.parse_args()

    analyzer = CacheAnalyzer(base_url=args.url)
    await analyzer.run_analysis(args.requests)


if __name__ == "__main__":
    asyncio.run(main())

