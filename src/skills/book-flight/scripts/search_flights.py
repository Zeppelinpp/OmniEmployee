#!/usr/bin/env python3
"""Mock flight search script that returns simulated flight data."""

import argparse
import json
import random
from datetime import datetime, timedelta


MOCK_AIRLINES = [
    {"code": "CA", "name": "Air China", "name_cn": "中国国际航空"},
    {"code": "MU", "name": "China Eastern", "name_cn": "东方航空"},
    {"code": "CZ", "name": "China Southern", "name_cn": "南方航空"},
    {"code": "HU", "name": "Hainan Airlines", "name_cn": "海南航空"},
    {"code": "JL", "name": "Japan Airlines", "name_cn": "日本航空"},
    {"code": "NH", "name": "ANA", "name_cn": "全日空"},
    {"code": "KE", "name": "Korean Air", "name_cn": "大韩航空"},
    {"code": "SQ", "name": "Singapore Airlines", "name_cn": "新加坡航空"},
    {"code": "CX", "name": "Cathay Pacific", "name_cn": "国泰航空"},
    {"code": "UA", "name": "United Airlines", "name_cn": "美联航"},
]

MOCK_AIRPORTS = {
    "Beijing": {
        "code": "PEK",
        "name": "Beijing Capital International Airport",
        "name_cn": "北京首都国际机场",
    },
    "Shanghai": {
        "code": "PVG",
        "name": "Shanghai Pudong International Airport",
        "name_cn": "上海浦东国际机场",
    },
    "Guangzhou": {
        "code": "CAN",
        "name": "Guangzhou Baiyun International Airport",
        "name_cn": "广州白云国际机场",
    },
    "Shenzhen": {
        "code": "SZX",
        "name": "Shenzhen Bao'an International Airport",
        "name_cn": "深圳宝安国际机场",
    },
    "Tokyo": {
        "code": "NRT",
        "name": "Narita International Airport",
        "name_cn": "东京成田国际机场",
    },
    "Seoul": {
        "code": "ICN",
        "name": "Incheon International Airport",
        "name_cn": "首尔仁川国际机场",
    },
    "Singapore": {
        "code": "SIN",
        "name": "Singapore Changi Airport",
        "name_cn": "新加坡樟宜机场",
    },
    "Hong Kong": {
        "code": "HKG",
        "name": "Hong Kong International Airport",
        "name_cn": "香港国际机场",
    },
    "New York": {
        "code": "JFK",
        "name": "John F. Kennedy International Airport",
        "name_cn": "纽约肯尼迪国际机场",
    },
    "Los Angeles": {
        "code": "LAX",
        "name": "Los Angeles International Airport",
        "name_cn": "洛杉矶国际机场",
    },
    "London": {
        "code": "LHR",
        "name": "London Heathrow Airport",
        "name_cn": "伦敦希思罗机场",
    },
    "Paris": {
        "code": "CDG",
        "name": "Paris Charles de Gaulle Airport",
        "name_cn": "巴黎戴高乐机场",
    },
}

# Flight duration estimates (in minutes)
ROUTE_DURATIONS = {
    ("Beijing", "Tokyo"): (180, 210),
    ("Beijing", "Seoul"): (120, 150),
    ("Beijing", "Shanghai"): (120, 150),
    ("Beijing", "Hong Kong"): (180, 210),
    ("Beijing", "Singapore"): (360, 420),
    ("Beijing", "New York"): (780, 840),
    ("Beijing", "Los Angeles"): (720, 780),
    ("Beijing", "London"): (600, 660),
    ("Shanghai", "Tokyo"): (150, 180),
    ("Shanghai", "Seoul"): (120, 150),
    ("Shanghai", "Hong Kong"): (150, 180),
    ("Guangzhou", "Tokyo"): (240, 270),
    ("Guangzhou", "Singapore"): (240, 270),
}


def get_airport(city: str) -> dict | None:
    """Get airport info by city name (case-insensitive)."""
    for name, info in MOCK_AIRPORTS.items():
        if name.lower() == city.lower():
            return {"city": name, **info}
    return None


def get_route_duration(from_city: str, to_city: str) -> tuple[int, int]:
    """Get estimated flight duration range for a route."""
    key = (from_city, to_city)
    reverse_key = (to_city, from_city)

    if key in ROUTE_DURATIONS:
        return ROUTE_DURATIONS[key]
    elif reverse_key in ROUTE_DURATIONS:
        return ROUTE_DURATIONS[reverse_key]
    else:
        # Default duration based on random estimate
        return (180, 300)


def generate_mock_flights(
    from_city: str,
    to_city: str,
    date: str,
    passengers: int = 1,
    cabin_class: str = "economy",
) -> list[dict]:
    """Generate mock flight data."""
    from_airport = get_airport(from_city)
    to_airport = get_airport(to_city)

    if not from_airport or not to_airport:
        return []

    flights = []
    num_flights = random.randint(3, 6)
    min_duration, max_duration = get_route_duration(from_city, to_city)

    # Base prices by cabin class (CNY)
    base_prices = {
        "economy": (1500, 4000),
        "business": (5000, 12000),
        "first": (10000, 25000),
    }

    price_range = base_prices.get(cabin_class.lower(), base_prices["economy"])

    # Generate departure times throughout the day
    departure_hours = sorted(random.sample(range(6, 22), min(num_flights, 8)))

    for i, hour in enumerate(departure_hours[:num_flights]):
        airline = random.choice(MOCK_AIRLINES)
        flight_number = f"{airline['code']}{random.randint(100, 999)}"

        # Calculate times
        departure_time = f"{hour:02d}:{random.randint(0, 5) * 10:02d}"
        duration_minutes = random.randint(min_duration, max_duration)

        dep_datetime = datetime.strptime(f"{date} {departure_time}", "%Y-%m-%d %H:%M")
        arr_datetime = dep_datetime + timedelta(minutes=duration_minutes)

        # Random stops
        stops = random.choices([0, 1, 2], weights=[0.6, 0.3, 0.1])[0]

        # Price calculation
        base_price = random.randint(*price_range)
        if stops == 0:
            base_price = int(base_price * 1.1)  # Direct flights cost more

        total_price = base_price * passengers

        flight = {
            "flight_number": flight_number,
            "airline": airline["name"],
            "airline_cn": airline["name_cn"],
            "departure": {
                "airport_code": from_airport["code"],
                "airport_name": from_airport["name_cn"],
                "city": from_airport["city"],
                "datetime": dep_datetime.strftime("%Y-%m-%d %H:%M"),
                "time": departure_time,
            },
            "arrival": {
                "airport_code": to_airport["code"],
                "airport_name": to_airport["name_cn"],
                "city": to_airport["city"],
                "datetime": arr_datetime.strftime("%Y-%m-%d %H:%M"),
                "time": arr_datetime.strftime("%H:%M"),
            },
            "duration": f"{duration_minutes // 60}h{duration_minutes % 60:02d}m",
            "duration_minutes": duration_minutes,
            "stops": stops,
            "stops_text": "Direct"
            if stops == 0
            else f"{stops} stop{'s' if stops > 1 else ''}",
            "cabin_class": cabin_class.capitalize(),
            "price_per_person": base_price,
            "total_price": total_price,
            "currency": "CNY",
            "seats_available": random.randint(1, 30),
            "baggage_allowance": "23kg" if cabin_class == "economy" else "32kg",
            "meal_included": cabin_class != "economy" or random.choice([True, False]),
        }
        flights.append(flight)

    # Sort by departure time
    flights.sort(key=lambda x: x["departure"]["datetime"])

    return flights


def format_flight_table(flights: list[dict]) -> str:
    """Format flights as a readable table."""
    if not flights:
        return "No flights found."

    lines = []
    lines.append("=" * 90)
    lines.append(
        f"{'Flight':<10} {'Departure':<18} {'Arrival':<18} {'Duration':<10} {'Price':<12} {'Stops'}"
    )
    lines.append("=" * 90)

    for f in flights:
        line = (
            f"{f['flight_number']:<10} "
            f"{f['departure']['time']} ({f['departure']['airport_code']})  "
            f"{f['arrival']['time']} ({f['arrival']['airport_code']})   "
            f"{f['duration']:<10} "
            f"¥{f['price_per_person']:<10,} "
            f"{f['stops_text']}"
        )
        lines.append(line)

    lines.append("=" * 90)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Search for available flights (mock data)"
    )
    parser.add_argument(
        "--from", dest="from_city", required=True, help="Departure city"
    )
    parser.add_argument("--to", dest="to_city", required=True, help="Destination city")
    parser.add_argument("--date", required=True, help="Departure date (YYYY-MM-DD)")
    parser.add_argument(
        "--return-date",
        dest="return_date",
        help="Return date for round trip (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--passengers", type=int, default=1, help="Number of passengers"
    )
    parser.add_argument(
        "--class",
        dest="cabin_class",
        default="economy",
        choices=["economy", "business", "first"],
        help="Cabin class",
    )
    parser.add_argument("--json", action="store_true", help="Output in JSON format")

    args = parser.parse_args()

    # Validate airports
    from_airport = get_airport(args.from_city)
    to_airport = get_airport(args.to_city)

    if not from_airport:
        print(f"Error: Unknown departure city '{args.from_city}'")
        print(f"Available cities: {', '.join(MOCK_AIRPORTS.keys())}")
        return

    if not to_airport:
        print(f"Error: Unknown destination city '{args.to_city}'")
        print(f"Available cities: {', '.join(MOCK_AIRPORTS.keys())}")
        return

    # Validate date
    try:
        departure_date = datetime.strptime(args.date, "%Y-%m-%d")
    except ValueError:
        print(f"Error: Invalid date format '{args.date}'. Use YYYY-MM-DD.")
        return

    print(f"\nSearching flights from {args.from_city} to {args.to_city}")
    print(
        f"Date: {args.date} | Passengers: {args.passengers} | Class: {args.cabin_class.capitalize()}"
    )
    print()

    # Generate outbound flights
    outbound_flights = generate_mock_flights(
        args.from_city, args.to_city, args.date, args.passengers, args.cabin_class
    )

    if args.json:
        result = {
            "search_params": {
                "from": args.from_city,
                "to": args.to_city,
                "date": args.date,
                "return_date": args.return_date,
                "passengers": args.passengers,
                "cabin_class": args.cabin_class,
            },
            "outbound_flights": outbound_flights,
        }

        if args.return_date:
            return_flights = generate_mock_flights(
                args.to_city,
                args.from_city,
                args.return_date,
                args.passengers,
                args.cabin_class,
            )
            result["return_flights"] = return_flights

        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Outbound: {args.from_city} → {args.to_city} ({args.date})")
        print(format_flight_table(outbound_flights))

        if args.return_date:
            print(f"\nReturn: {args.to_city} → {args.from_city} ({args.return_date})")
            return_flights = generate_mock_flights(
                args.to_city,
                args.from_city,
                args.return_date,
                args.passengers,
                args.cabin_class,
            )
            print(format_flight_table(return_flights))


if __name__ == "__main__":
    main()
