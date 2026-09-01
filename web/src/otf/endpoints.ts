/**
 * OTF data API endpoint calls.
 *
 * Each call obtains a fresh, valid Cognito ID token, attaches it as
 * `Authorization: Bearer <id_token>`, adds any endpoint-specific headers, and
 * dispatches through the configured Transport. Responses are returned raw;
 * normalize.ts maps them into the local Dexie schema.
 */

import { getValidIdToken, type MemberIdentity } from "./auth";
import { defaultTransport, type Transport } from "./transport";
import { HOST_IO, HOST_TELEMETRY, HOST_CO } from "./config";

/** Raw OTF performance-summary list item (shape kept loose; see normalize.ts). */
export type RawPerfSummary = Record<string, unknown>;
export type RawPerfDetail = Record<string, unknown>;
export type RawTelemetry = Record<string, unknown>;

export class OtfClient {
  constructor(
    private readonly identity: MemberIdentity,
    private readonly transport: Transport = defaultTransport(),
  ) {}

  private async authHeaders(extra?: Record<string, string>): Promise<Record<string, string>> {
    const token = await getValidIdToken();
    return { Authorization: `Bearer ${token}`, ...(extra ?? {}) };
  }

  /** Headers required by the api.orangetheory.io performance-summary endpoints. */
  private kojiHeaders(): Record<string, string> {
    return {
      "koji-member-id": this.identity.memberUuid,
      "koji-member-email": this.identity.email,
    };
  }

  /** List performance summaries (one entry per workout). `limit` caps the count. */
  async listPerfSummaries(limit = 1000): Promise<RawPerfSummary[]> {
    const headers = await this.authHeaders(this.kojiHeaders());
    const res = await this.transport.request<{ items?: RawPerfSummary[] }>({
      host: HOST_IO,
      path: "/v1/performance-summaries",
      query: { limit },
      headers,
    });
    return res.items ?? [];
  }

  /** Fetch the detailed performance summary for a single workout. */
  async getPerfSummary(perfSummaryId: string): Promise<RawPerfDetail> {
    const headers = await this.authHeaders(this.kojiHeaders());
    return this.transport.request<RawPerfDetail>({
      host: HOST_IO,
      path: `/v1/performance-summaries/${perfSummaryId}`,
      headers,
    });
  }

  /** Fetch the per-second telemetry (HR / tread / rower) for a workout. */
  async getTelemetry(perfSummaryId: string, maxDataPoints = 150): Promise<RawTelemetry> {
    const headers = await this.authHeaders();
    return this.transport.request<RawTelemetry>({
      host: HOST_TELEMETRY,
      path: "/v1/performance/summary",
      query: { classHistoryUuid: perfSummaryId, maxDataPoints },
      headers,
    });
  }

  /** Body composition records (uses the Cognito id, not the member uuid). */
  async getBodyComposition(): Promise<unknown> {
    const headers = await this.authHeaders();
    return this.transport.request({
      host: HOST_CO,
      path: `/member/members/${this.identity.cognitoId}/body-composition`,
      headers,
    });
  }

  /** Challenge / benchmark results. */
  async getBenchmarks(): Promise<unknown> {
    const headers = await this.authHeaders();
    return this.transport.request({
      host: HOST_CO,
      path: `/challenges/v3/member/${this.identity.memberUuid}/benchmarks`,
      headers,
    });
  }

  /** Member lifetime stats over a time window (AllTime, Last30Days, ...). */
  async getLifetimeStats(selectTime = "AllTime"): Promise<unknown> {
    const headers = await this.authHeaders();
    return this.transport.request({
      host: HOST_CO,
      path: `/performance/v2/${this.identity.memberUuid}/over-time/${selectTime}`,
      headers,
    });
  }
}
