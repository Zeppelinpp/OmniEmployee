#!/usr/bin/env python3
"""Mock flight booking confirmation script."""

import argparse
import json
import random
import string
from datetime import datetime


def generate_booking_reference() -> str:
    """Generate a random booking reference code."""
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=6))


def generate_ticket_number() -> str:
    """Generate a mock e-ticket number."""
    prefix = random.choice(["999", "880", "781", "086"])
    number = "".join(random.choices(string.digits, k=10))
    return f"{prefix}-{number}"


def confirm_booking(
    flight_number: str,
    date: str,
    passengers: list[dict],
    contact_email: str = None,
    contact_phone: str = None,
) -> dict:
    """Generate a mock booking confirmation."""
    booking_ref = generate_booking_reference()
    booking_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    passenger_tickets = []
    for passenger in passengers:
        passenger_tickets.append(
            {
                "name": passenger.get("name", "Passenger"),
                "ticket_number": generate_ticket_number(),
                "seat": f"{random.randint(1, 40)}{random.choice('ABCDEF')}",
                "meal_preference": passenger.get("meal", "Standard"),
            }
        )

    confirmation = {
        "status": "CONFIRMED",
        "booking_reference": booking_ref,
        "booking_time": booking_time,
        "flight_number": flight_number,
        "flight_date": date,
        "passengers": passenger_tickets,
        "contact": {
            "email": contact_email or "not_provided@example.com",
            "phone": contact_phone or "Not provided",
        },
        "important_notes": [
            "Please arrive at the airport at least 2 hours before departure for domestic flights, 3 hours for international flights.",
            "Carry a valid ID/passport that matches the name on your ticket.",
            "Online check-in opens 24 hours before departure.",
            "This is a MOCK booking for demonstration purposes only.",
        ],
    }

    return confirmation


def format_confirmation(confirmation: dict) -> str:
    """Format booking confirmation for display."""
    lines = []
    lines.append("=" * 60)
    lines.append("         ✈️  FLIGHT BOOKING CONFIRMATION  ✈️")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"  Booking Reference: {confirmation['booking_reference']}")
    lines.append(f"  Status: {confirmation['status']}")
    lines.append(f"  Booking Time: {confirmation['booking_time']}")
    lines.append("")
    lines.append("-" * 60)
    lines.append("  FLIGHT DETAILS")
    lines.append("-" * 60)
    lines.append(f"  Flight: {confirmation['flight_number']}")
    lines.append(f"  Date: {confirmation['flight_date']}")
    lines.append("")
    lines.append("-" * 60)
    lines.append("  PASSENGER INFORMATION")
    lines.append("-" * 60)

    for i, p in enumerate(confirmation["passengers"], 1):
        lines.append(f"  Passenger {i}: {p['name']}")
        lines.append(f"    E-Ticket: {p['ticket_number']}")
        lines.append(f"    Seat: {p['seat']}")
        lines.append(f"    Meal: {p['meal_preference']}")
        lines.append("")

    lines.append("-" * 60)
    lines.append("  CONTACT INFORMATION")
    lines.append("-" * 60)
    lines.append(f"  Email: {confirmation['contact']['email']}")
    lines.append(f"  Phone: {confirmation['contact']['phone']}")
    lines.append("")
    lines.append("-" * 60)
    lines.append("  IMPORTANT NOTES")
    lines.append("-" * 60)
    for note in confirmation["important_notes"]:
        lines.append(f"  • {note}")
    lines.append("")
    lines.append("=" * 60)
    lines.append("  Thank you for your booking!")
    lines.append("=" * 60)

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Confirm a flight booking (mock)")
    parser.add_argument("--flight", required=True, help="Flight number")
    parser.add_argument("--date", required=True, help="Flight date (YYYY-MM-DD)")
    parser.add_argument(
        "--passengers",
        required=True,
        help='Passenger info as JSON string, e.g., \'[{"name": "John Doe"}]\'',
    )
    parser.add_argument("--email", help="Contact email")
    parser.add_argument("--phone", help="Contact phone")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")

    args = parser.parse_args()

    # Parse passengers
    try:
        passengers = json.loads(args.passengers)
        if not isinstance(passengers, list):
            passengers = [passengers]
    except json.JSONDecodeError:
        # Treat as single passenger name
        passengers = [{"name": args.passengers}]

    # Generate confirmation
    confirmation = confirm_booking(
        flight_number=args.flight,
        date=args.date,
        passengers=passengers,
        contact_email=args.email,
        contact_phone=args.phone,
    )

    if args.json:
        print(json.dumps(confirmation, indent=2, ensure_ascii=False))
    else:
        print(format_confirmation(confirmation))


if __name__ == "__main__":
    main()
