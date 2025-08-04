# cancel_pending_order

Tool Prompt for cancel_pending_order

## When to call the tool
- Use this tool to cancel a PENDING order entirely, with explicit user confirmation. The order must not be shipped or delivered yet. Inform the user that the full order will be cancelled and the refund will be processed according to the payment method.
- Do NOT use this tool for requests to cancel or remove an individual item from an order (partial cancellations are NOT supported by any available tool).

## Before calling the tool
Required Parameters:
- `order_id`: The pending order ID to be cancelled (be sure of the order by confirming with the user and reviewing order details).
- `reason`: The reason, either 'no longer needed' or 'ordered by mistake'; select the one that best matches the user's stated reason.

User Confirmation:
- Clearly explain that the ENTIRE order will be cancelled and all items in that order will be refunded according to the payment method. If the user only wants to cancel specific items, inform them that partial cancellations are not possible — only full order cancellations can be processed with this tool. Ask for explicit confirmation (yes/no) to proceed before execution.

Handling Conditional User Requests:
- If the user requests a specific refund method (e.g., gift card instead of credit card), explain that the refund must go to the original payment method unless the order was purchased on a gift card. Only proceed if the user agrees to this limitation.

Common Mistakes to Avoid:
- Do NOT use this tool for delivered or processed orders — confirm status first.
- Do NOT attempt to use this tool to remove or cancel an individual item from an order.
- Do NOT commit to a conditional cancellation (e.g., 'I will only cancel if refunded to gift card') unless the tool supports the required condition.
- Do NOT make multiple tool calls at once; execute this as a single, separate action.

## After calling the tool
- Inform the user of the cancellation result: entire order has been cancelled, items will not be shipped, and the refund method and timeline.
- If you cannot meet the user's condition (e.g., can't refund to a different method), clearly state the limitation and offer alternatives if available.

## Example
- Correct: 'You asked to cancel order #W8855135. This will cancel ALL items in your order and refund your card. Do you confirm?' Proceed only after confirmation.
- Incorrect: Accepting and cancelling a single item using this tool, or ignoring user conditions about refund methods that are not supported.