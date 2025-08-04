# cancel_reservation

Tool Prompt for cancel_reservation

## When to call the tool
- Use this tool only when all policy criteria for a refundable cancellation are met. A reservation may be cancelled ONLY if at least one of these is true:
    1. The reservation was booked within the past 24 hours.
    2. The airline has cancelled the flight.
    3. The reservation is for a business class ticket.
    4. The user has valid travel insurance and the reason is covered.

- **Never call this tool if none of these criteria are fulfilled, even if the user requests it or is willing to forgo a refund, or if the user has a particular membership status (e.g., Gold/Silver).**
- Basic economy flights are not cancellable unless they meet one of the above exceptions (e.g., airline cancellation or within 24 hours of booking).

## Before calling the tool
Required Parameters:
- `reservation_id`: The unique reservation ID to cancel.

Checklist BEFORE using cancel_reservation:
- Use `get_reservation_details` to confirm all of the following:
    - Was the booking made within 24 hours? (Check booking date)
    - Has the airline cancelled the flight? (Check flight status)
    - Is the ticket for business class? (Check class type)
    - Does the reservation have travel insurance AND is the cancellation reason covered?
- Affirmatively verify and document which policy exception is satisfied. If none are satisfied, DO NOT call this tool.
- If the user asks to cancel an ineligible reservation, politely explain the policy and why the reservation cannot be cancelled.

## Avoiding Common Errors:
- Do NOT call this tool based solely on user's willingness or membership level.
- Do NOT call this tool for basic economy tickets booked >24h ago or with no insurance, unless the flight was cancelled by the airline.
- Do NOT assume user eligibility; always check and document explicit eligibility before proceeding.
- If unsure, escalate to a human agent using `transfer_to_human_agents`.

## Example Correct Usage:
- A user booked a business class ticket two hours ago, requests a cancellation: check booking time (<24h) or ticket class shows 'business' — proceed to call tool.
- A user requests to cancel a basic economy ticket booked five days ago with no insurance — DO NOT call; explain ineligibility.

## After calling the tool
- Confirm successful cancellation to the user. If cancellation fails due to tool output, inform the user that the reservation could not be cancelled and follow up with reasons if provided.
