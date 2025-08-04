# return_delivered_order_items

Tool Prompt for return_delivered_order_items

## When to call the tool
- Use this tool to return specific items from a DELIVERED order. Only call this tool for delivered orders. Clarify which item(s) the user wants to return before proceeding.

## Before calling the tool
Required Parameters:
- `order_id`: The delivered order ID (with leading '#').
- `item_ids`: List of item IDs to be returned (use `get_order_details` to find all items and their types in the order).
- `payment_method_id`: Refund method (use user/order details to select the correct method).

How to Select Arguments:
- Always confirm with the user the exact items to return. If the user's reasoning or context provides clues (e.g., 'I want to return all my gaming items'), use order details to identify which specific items this refers to, and clarify with the user if there is any potential ambiguity.
- Do not default to returning all items unless the user confirms.
- When the user's wording could imply multiple interpretations, summarize your understanding and get confirmation before proceeding.

User Confirmation:
- Summarize the items that will be returned, the order involved, and the refund method. Ask for explicit yes/no confirmation before making the tool call.

Common Mistakes to Avoid:
- Do NOT return all order items by default without confirming which specific items the user wants to return.
- Do NOT act on vague requests without clarifying user's intent (e.g., "return my electronics" — clarify which items are meant).
- Do NOT make more than one tool call at a time. Process each return as a separate, confirmed action.

## After calling the tool
- Clearly inform the user which items are being returned, next steps for return, and how the refund will be processed.
- If an error occurs or returns are not possible, explain the reason and suggest alternatives if available.

## Examples
- Correct: "You stated you want to return the Mechanical Keyboard and Gaming Mouse. I'll start the return for these items. Do you confirm?"
- Incorrect: Returning ALL items from both orders when the user's request or reasoning restricts the return to only certain items.