# exchange_delivered_order_items

Tool Prompt for exchange_delivered_order_items

## When to call the tool
- Use this tool only to exchange specific items in a DELIVERED order for new items of the SAME PRODUCT TYPE (e.g., exchange a delivered blue t-shirt for a delivered green t-shirt).
- Order must have status 'delivered'. Confirm the order and item(s) to exchange by retrieving and reviewing order details before proceeding.

## Before calling the tool
Required Parameters: You must provide:
- `order_id`: The ID of the delivered order (must begin with '#').
- `item_ids`: List of item IDs from the order to be exchanged.
- `new_item_ids`: List of replacement item IDs, each matched by position and product type to `item_ids`.
- `payment_method_id`: Payment method for paying/receiving price difference (find in user or order details).

User Confirmation:
- Clearly explain to the user which item(s) will be exchanged, for what replacements, and any price differences/refunds. Ask for explicit confirmation (yes/no) before calling the tool.

Retrieving Arguments:
- Use `get_order_details` to find all delivered orders and clarify which order/item(s) the user wants to exchange if not specified.
- Use `get_product_details` to locate valid replacement items. Ensure you pick items with 'available': true.
- If the user's description is ambiguous (e.g., "exchange for the same as my other earbuds"), ask clarifying questions or retrieve relevant details before acting.

Common Mistakes to Avoid:
- Do NOT use this tool for pending or processed orders—verify order status.
- Ensure each `new_item_id` is of the SAME PRODUCT TYPE as the item being exchanged.
- Do not attempt to remove items; the tool only supports exchanges, not item removals.
- Only call this tool ONCE per order (one exchange allowed per delivered order).
- Never call this tool at the same time as another modifying tool; make only one tool call per turn.
- Make sure item IDs and replacement IDs are accurate and not for unavailable products.

## After calling the tool
- Check the response to confirm the exchange and communicate the results clearly to the user (what will be shipped, how refunds or payments will be processed).
- If the tool fails (e.g., unavailable product or order status), inform the user and offer alternative solutions if possible.

## Examples
- Correct: "You want to exchange your delivered blue t-shirt for a black one. I will process the exchange for these items. Do you confirm?"
- Incorrect: Calling this tool to exchange items in pending orders (use `modify_pending_order_items` instead). 
- Incorrect: Proposing to exchange for an unavailable variant or the same item (no change).
- Correct: Use the correct payment method for settling price differences.