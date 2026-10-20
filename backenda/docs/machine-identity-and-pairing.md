# Machine Identity, Pairing, and Role Enforcement

This document specifies the cryptographic machine identity architecture, browser-to-agent pairing workflow, role enforcement invariants, and security boundaries in ADC.

---

## 1. Machine Identity Architecture

In ADC, **User Identity** (human accounts) and **Machine Identity** (computing hardware nodes) are strictly segregated.

### Cryptographic Identity Lifecycle
1. **Installation:** When an ADC agent starts for the first time, it generates:
   - A cryptographically random `installation_id` (prefixed with `inst_`, using 16 bytes of entropy).
   - An **Ed25519** asymmetric key pair (Edwards-curve Digital Signature Algorithm).
2. **Local Persistence:** The private key is serialized as PKCS#8 PEM and stored in `~/.adc/machine_identity.json` (or the location defined by `$ADC_IDENTITY_FILE`). File permissions are restricted to the current user.
3. **Backend Registration:** The public key (64 hex characters, representing 32 raw bytes) is registered with the backend via `POST /api/v1/machines/register`.
4. **Challenge-Response Authentication:** On all subsequent sensitive agent requests (e.g. initiating pairing), the agent signs `{installation_id}:{timestamp}` using its Ed25519 private key. The backend verifies the signature against the registered public key, rejecting timestamps older than 300 seconds to prevent replay attacks.

### Limitations of Software-Only Device Identification
> [!IMPORTANT]
> ADC does **not** rely on MAC addresses, hostnames, IP addresses, or browser user-agent strings for primary machine identity:
> - IP addresses are shared behind corporate/residential NATs and change frequently on DHCP.
> - MAC addresses and hostnames are trivial to spoof or virtualize in software.
>
> **Known Security Boundary:** Software-only cryptographic identity guarantees proof of key possession under standard operating conditions. However, if an attacker has root/administrator privileges on the host or copies a virtual machine image, the private key file can be cloned. True hardware-bound identity requires TPM 2.0 / Apple Secure Enclave sealing, which is noted as an operational limit of software-only agent installations.

---

## 2. Secure Browser-to-Agent Pairing Flow

The pairing process securely links a running local agent process to an authenticated web user:

```
+--------------------+              +--------------------+             +--------------------+
|    Agent (CLI)     |              |     ADC Backend    |             |   Web App / User   |
+--------------------+              +--------------------+             +--------------------+
          |                                   |                                   |
          |  1. POST /pairing/challenge       |                                   |
          |     (with Ed25519 signature)      |                                   |
          |---------------------------------->|                                   |
          |                                   |                                   |
          |  2. Returns 6-char code "ABC123"  |                                   |
          |<----------------------------------|                                   |
          |                                   |                                   |
          |  [Displays: Code ABC123]          |                                   |
          |                                   |  3. User enters ABC123 in UI      |
          |                                   |     POST /pairing/complete        |
          |                                   |     { code, selected_role }       |
          |                                   |<----------------------------------|
          |                                   |                                   |
          |                                   |  4. Validates challenge,          |
          |                                   |     Enforces One Machine One Role,|
          |                                   |     Binds machine to user,        |
          |                                   |     Issues instance lease token   |
          |                                   |---------------------------------->|
          |                                   |                                   |
          |  5. Polls /machines/me            |                                   |
          |     (Receives role & lease)       |                                   |
          |<----------------------------------|                                   |
          |                                   |                                   |
          |  6. Periodic Heartbeat Loop       |                                   |
          |     POST /machines/heartbeat      |                                   |
          |---------------------------------->|                                   |
```

### Security Safeguards
- **Entropy & Legibility:** 6-character alphanumeric code using un-ambiguous characters (`23456789ABCDEFGHJKMNPQRSTUVWXYZ`), avoiding confusion between `0/O` and `1/I/L`.
- **Short TTL:** Pairing challenges expire automatically after 5 minutes (300 seconds).
- **Single-Use:** Once used, the status is irrevocably set to `completed`.
- **Brute-Force Lockout:** After 5 failed attempts, the challenge status transitions to `failed` and is locked permanently.
- **Zero Key Leakage:** Private keys are never transmitted over the network or exposed to the browser.

---

## 3. "One Machine, One Role" Enforcement

ADC enforces that a physical/virtual machine registration can hold **only one active role** at any time:

$$\text{Active Role} \in \{\text{'none'}, \text{'master'}, \text{'worker'}\}$$

1. **Backend Verification:** Role constraints are enforced in database fields and API transaction boundaries, never delegated solely to frontend checks.
2. **Active Instance Leases:**
   - When an agent connects, it is granted an active lease with a lease token and an expiration timestamp (default: 300 seconds).
   - The agent maintains this lease by sending heartbeats every 25 seconds (`POST /api/v1/machines/heartbeat`).
   - If a second agent process attempts to connect from the same machine with a conflicting lease, it is rejected with `409 Conflict`.
3. **Controlled Role Transitions:**
   - Role switching (`POST /api/v1/machines/role-change`) is disallowed while `status == 'training'` to prevent corrupting active distributed jobs.
   - Stale sessions from terminated processes are reconciled safely once `lease_expires_at` has elapsed.
4. **Revocation:**
   - Calling `POST /api/v1/machines/revoke` revokes machine credentials, clears all active leases, resets role to `'none'`, and removes user association.
