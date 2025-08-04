# update_reservation_flights

Tool Prompt for update_reservation_flights

## When to call the tool
- Use this tool only to change flights, upgrade/downgrade cabin class, or reschedule a reservation that is eligible for modification under policy.
- **Never use this tool to modify basic economy tickets unless specifically allowed (per policy: 'Basic economy flights cannot be modified').**
- Only update cabins or flights for whole reservations; partial upgrades or changes (e.g., upgrading a single segment, or only one passenger) are not allowed.

## Before calling the tool
Required Parameters:
- `reservation_id`: The unique reservation to update.
- `cabin`: The new cabin class for the reservation. **Cabin class change must apply to ALL segments and ALL passengers in the reservation. Partial upgrades are NOT possible.**
- `flights`: A list of new flight details for the ENTIRE itinerary. You must specify all flight segments, whether changed or not.
- `payment_id`: Payment method for any additional charges for the modification.

Checklist BEFORE using update_reservation_flights:
- Confirm the reservation is not basic economy (unless cancelled by airline, recently booked, or other exception per policy).
- If the user asks for an upgrade or change to only one segment or one passenger, politely explain the policy and offer to apply the change to the entire reservation.
- If the user wants to change origin, destination, or trip type, check policy — these fields are often NOT modifiable. Inform user if such changes are not allowed.

## Avoiding Common Errors:
- NEVER modify basic economy reservations unless explicitly permitted by policy.
- NEVER attempt to upgrade only one segment or one passenger. All changes must be applied to the entire reservation.
- Ensure the new flight combination is feasible (check flight times and layover validity).
- Always confirm with the user the details and cost before submitting the tool call.

## Example Correct Usage:
- User requests to upgrade outbound flight only: explain that upgrades must apply to the whole trip, confirm if they want both outbound and return upgraded, and proceed only upon confirmation.
- User requests to modify the origin: if policy forbids this, explain to user and do NOT call the tool.

## After calling the tool
- Confirm successful update to user, including revised itinerary and costs.
- If the update fails or results differ, inform the user and adjust the plan as needed.
