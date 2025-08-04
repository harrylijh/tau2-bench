# modify_pending_order_items

Tool Prompt for modify_pending_order_items

## When to call the tool
- Use this tool to modify (exchange) items in a PENDING order to new items of the same product type — for example, if the user wishes to change the color, size, or version of an item they have already ordered, as long as the product type stays the same (e.g., shirt to shirt, not shirt to shoes).
- The order must be in 'pending' status. Always confirm status with `get_order_details` before proceeding.

## Before calling the tool
Required Parameters:
- `order_id`: The ID of the pending order (always starts with '#').
- `item_ids`: List of existing item IDs in the order to be modified/specified for exchange.
- `new_item_ids`: List of new item IDs to replace each item in `item_ids`, matched in order and with the SAME PRODUCT TYPE. Each list must have the same length. You CANNOT remove items or submit an empty list—every slot must have a corresponding new item of the same type.
- `payment_method_id`: Payment method to make or receive payments for price differences (retrieve from user or order details).

User Confirmation:
- Always summarize the intended modification, item by item, and request explicit user confirmation (yes/no) before making the tool call. Wait for confirmation before proceeding.

How to Select Arguments:
- Use `get_product_details` to find available, in-stock item variants for use as replacements.
- For requests like 'cheapest', 'most expensive', or size/option-specific changes, parse the output and select the item that truly matches the specified user criteria AND is available.
- If the user requests to exchange for a different size or version, ensure the replacement is both available and matches the user's specific requirements (e.g., do not select a different size unless the user authorizes it).
- DO NOT submit empty or incomplete lists for `new_item_ids`—removing items is not supported.
- For ambiguous requests, clarify with the user before acting.

Common Mistakes to Avoid:
- Do NOT attempt to remove items by submitting blank or empty `new_item_ids`. This tool is for exchanges, not removals.
- Do NOT propose to exchange for items that are unavailable, the same as the original, or across product types.
- Always ensure the length of `new_item_ids` matches `item_ids` and maps item-for-item.
- Never make more than one tool call in a single turn; always make only one modification per turn.

## After calling the tool
- Verify the tool's response and summarize the successful changes to the user. If an error occurs (wrong product type, unavailable replacement, etc.), inform the user and offer to try again or propose alternatives.

## Examples
- Correct: "You want to exchange your size 9 running shoes for a size 9, red version. I'll change that for you. Do you confirm?"
- Incorrect: Using `new_item_ids: []` to attempt to remove items.
- Incorrect: Exchanging for an unavailable or different-size item unless explicitly approved by the user.
- Correct: For upgrades/downgrades ('cheapest', 'most expensive'), always check product availability and user constraints (e.g., color, size).