# calculate

Tool Prompt for calculate

## When to call the tool
- Use this tool whenever a user asks for a total price, refund amount, price difference, or other calculated financial value that is not directly available from other tools. Always provide users with a clear calculation of sums or differences using item prices obtained from order/product details.

## How to Use the Tool
Required Parameter:
- `expression`: Enter an explicit mathematical expression (e.g., '235.13 + 346.97 + 511.24') that matches the user's request. Gather item prices using `get_order_details` or `get_product_details` first if needed.

Common Mistakes to Avoid:
- Do NOT skip the calculation when the user has asked for an explicit sum or refund amount. Always call the tool and provide the result before progressing the conversation.
- Do NOT estimate or hallucinate totals—use precise figures from retrieved data and the 'calculate' tool.

## Examples
- Correct: "To calculate your refund, I'll sum the prices: 235.13 + 346.97 + 511.24. This totals $1093.34."
- Incorrect: Failing to answer a user's direct calculation question after retrieving item prices.