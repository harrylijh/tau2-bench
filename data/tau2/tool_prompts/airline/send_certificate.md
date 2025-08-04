# send_certificate

Tool Prompt for send_certificate

## When to call the tool
- Use ONLY when the user explicitly requests compensation in the form of a certificate, or customer care policy requires it in response to a documented service failure (as per explicit scenario). 
- DO NOT proactively send compensation or offer travel certificates unless the user explicitly asks for it, regardless of the circumstances (e.g., flight disruption, cancellation, complaint).

## Before calling the tool
Required Parameters:
- `user_id`: The unique ID of the user to receive the certificate.
- `amount`: The dollar amount for the certificate.

Checklist BEFORE using send_certificate:
- Confirm with the user their request or explicit acceptance of compensation.
- Do not propose or issue certificates preemptively.
- Ensure the compensation amount is justified based on company policy or user request.

## Avoiding Common Errors:
- Do not send certificates automatically after cancellations or delays unless the user requests it.
- Never offer compensation on your initiative.
- If the user expects a certificate and it is not warranted per policy, explain this and do not call the tool.
