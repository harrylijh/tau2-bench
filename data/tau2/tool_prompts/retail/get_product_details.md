# get_product_details

Tool Prompt for get_product_details

## When to call the tool
- Use this tool to find out about all available and unavailable variants of a given product type (options, attributes such as color, size, price, etc.). Use when assisting users with selection, modification, or exchange of items.

## After calling the tool
- When interpreting the output, always carefully distinguish between the total list of variants and those with 'available': true. Only include available options when reporting availability, making selections, or offering choices to the user unless otherwise requested.
- For requests about 'cheapest', 'most expensive', or 'currently available' options, always filter for items with 'available': true and select among those.
- If selecting by price or attribute (e.g., cheapest, size, color), parse prices and attributes carefully across available variants only—do not include unavailable variants in the selection.

Common Mistakes to Avoid:
- Do NOT report the total number of variants as 'available'—always count only those with 'available': true.
- Never select unavailable or out-of-stock options when proposing exchanges or modifications.
- If user makes a broad request but only some variants are available, clarify with the user if their preference matches current availability.

## Examples
- Correct: "There are 10 available t-shirt options at the moment."
- Incorrect: "There are 12 available t-shirt options," when only 10 have 'available': true.
- Correct: When asked for the 'cheapest' air purifier, select the item with the lowest price among those with 'available': true.