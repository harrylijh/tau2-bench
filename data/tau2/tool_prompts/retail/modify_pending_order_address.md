# modify_pending_order_address

Tool Prompt for modify_pending_order_address

## When to call the tool
- Use this tool only to modify the shipping address of a PENDING order. Confirm that the order status is 'pending' before proceeding.
- If the user requests to update the shipping address for multiple orders, process each one individually with user confirmation per order.

## Before calling the tool
Required Parameters:
- `order_id`: The pending order ID (start with '#') to update.
- `address1`, `address2`, `city`, `state`, `country`, `zip`: The full new address, confirmed and clarified with the user.

User Confirmation:
- Always summarize the new address, explain that you will change the shipping address for order #[order_id], and ask for explicit confirmation (yes/no) to proceed. WAIT for confirmation before making the tool call. Do NOT call the tool in the same turn as proposing the change.
- For multiple pending orders, repeat this confirmation and tool call process for each order, one at a time.

Common Mistakes to Avoid:
- Never update addresses for orders that are not pending.
- Never skip user confirmation before making the change.
- Never make more than one tool call per turn (process each change individually).
- Always confirm both the old and new address with the user if any ambiguity exists (for instance, if the user seems confused about which address is "old" and which is "new").
- Do not confuse this tool with `modify_user_address`, which updates the profile address for future orders only.

## After calling the tool
- Confirm the address has been updated for the specified order and summarize the result for the user.
- For multiple orders, confirm to the user after each update.

## Examples
- Correct: "You want to change the shipping address for order #W9583042 to 12 Ivy Lane, Boston, MA, USA 02130. Do you confirm?"
- Incorrect: Changing the address without explicit user confirmation in the prior response.
- Incorrect: Updating only one order when the user requested changes for multiple pending orders.