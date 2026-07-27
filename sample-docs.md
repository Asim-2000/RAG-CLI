# Internal Payments API

## Overview
The Payments API lets internal services create and refund charges against a
customer's stored payment method. Base URL: `https://internal.api.company.com/payments/v1`.

## Authentication
All requests require a bearer token in the `Authorization` header. Tokens are
obtained from the internal Auth service:

```
POST /v1/auth/token
Body: { "client_id": "...", "client_secret": "..." }
```

Tokens are valid for 1 hour. There is no refresh endpoint — request a new
token when the old one expires.

## Rate limits
- 100 requests/minute per client_id on `POST /charges`
- 1000 requests/minute per client_id on `GET` endpoints
- Exceeding the limit returns `429 Too Many Requests` with a `Retry-After` header

## Endpoints

### Create a charge
```
POST /charges
Headers: Authorization: Bearer <token>
Body: {
  "customer_id": "cus_123",
  "amount_cents": 1999,
  "currency": "usd",
  "idempotency_key": "unique-string-per-attempt"
}
```
Returns `201 Created` with a `charge_id`. Always pass `idempotency_key` —
retries without it can double-charge the customer.

### Get a charge
```
GET /charges/{charge_id}
```
Returns charge status: `pending`, `succeeded`, `failed`, or `refunded`.

### Refund a charge
```
POST /charges/{charge_id}/refund
Body: { "amount_cents": 1999 }
```
Partial refunds are supported — omit `amount_cents` to refund the full amount.
Refunds are final and cannot be reversed.

## Error codes
| Code | Meaning |
|---|---|
| `insufficient_funds` | Customer's payment method was declined |
| `invalid_customer` | `customer_id` does not exist |
| `duplicate_idempotency_key` | A charge already exists for this key; the original charge is returned instead of creating a new one |

## Common pitfalls
- Forgetting `idempotency_key` on retries after a timeout is the #1 cause of
  duplicate charges. Always set it.
- `amount_cents` is an integer in the smallest currency unit (cents for USD),
  not a decimal dollar amount.
- The Payments API does not store card numbers — that's handled entirely by
  the Vault service; Payments only ever sees a `customer_id` token.