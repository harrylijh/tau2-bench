# book_reservation

Tool Prompt for book_reservation

## When to call the tool
- Use to book new reservations only after confirming all trip details, passenger information, and payment preferences with the user.

## Before calling the tool
Required Parameters:
- `user_id`, `origin`, `destination`, `flight_type`, `cabin`, `flights`, `passengers`, `payment_methods`, `total_baggages`, `nonfree_baggages`, and `insurance`.

Checklist BEFORE using book_reservation:
- Ensure you have all required input values.
- For `payment_methods`:
    - **Policy: Only ONE travel certificate per booking.** If a user provides multiple certificates, use the largest value only, and cover the remaining balance with a secondary method (e.g., credit card, gift card) as instructed by the user.
    - If user gives conditional payment instructions (e.g., "Use gift card if certificate waste > $100"), process their condition carefully and follow exactly (calculate waste/refund, compare against threshold, and choose payment accordingly).
- When searching for flights:
    - Fully consider all user constraints ("anywhere West Coast" = SEA, LAX, SFO, etc.), not just the most common airports.
    - For requests like "cheapest," "fastest," or "second cheapest," process all options and validate your choice before presenting to the user.
- Double-check all calculations (fares, balances, etc.), and confirm final charges with user before booking.

## Avoiding Common Errors:
- NEVER use more than one certificate in the booking, even if user provides several.
- Always match user payment preferences, including any conditions on payment method use.
- If user asks for cheapest, second cheapest, or fastest, verify and present the correct option based on comprehensive search.
- Do not subtract previous payments from new booking prices unless policy explicitly allows; treat them as separate transactions with refunds handled independently.

## Example Correct Usage:
- User gives two certificates, wants to use both: Use only the one with the highest value, then use other specified methods (per policy).
- User gives a conditional payment instruction (use certificate only if waste is < $100): Correctly calculate waste, compare to threshold, and confirm with user.
- User requests 'cheapest West Coast flight': Search all major and minor west coast airports, not just LAX or SFO.

## After calling the tool
- Confirm reservation details, payment breakdown, and charges with the user. Seek user confirmation if there are any changes from the presented options.