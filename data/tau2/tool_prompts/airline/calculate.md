# calculate

Tool Prompt for calculate

## When to call the tool
- Use this tool to perform straightforward arithmetic operations or conversions explicitly required to fulfill a user's request (price calculation, baggage fees, refunds, etc.).

## Before calling the tool
Required Parameters:
- `expression`: The arithmetic expression to evaluate.

Checklist BEFORE using calculate:
- Double-check calculation logic to ensure it matches company policy and standard financial procedures (e.g., do not subtract prior payments directly from total new bookings unless policy and process explicitly allows this).
- For cancel-and-rebook scenarios, confirm: old reservations are refunded separately; new bookings are charged in full.

## Avoiding Common Errors:
- Do not assume previous payments can be directly netted against new charges, unless policy permits.
- Use the tool for discrete calculations, not complex workflows.
- Always confirm computed amounts by clearly showing the steps to the user.

## Example Correct Usage:
- 'New fare is $871, old fare is $189, refund will be processed separately, and $871 is charged to your card.'
- Do NOT say 'You will pay $682 (=871-189) for the new booking' unless policy says so — instead, explain both transactions independently.