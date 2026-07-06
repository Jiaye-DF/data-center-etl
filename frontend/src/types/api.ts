/** 後端統一回應信封(FastAPI `ApiResponse[T]`) */
export interface ApiEnvelope<T> {
  success: boolean
  data: T | null
  detail: string | null
  response_code: number
}

export function unwrap<T>(envelope: ApiEnvelope<T>): T {
  if (envelope.data === null) {
    throw new Error(envelope.detail ?? 'empty_response')
  }
  return envelope.data
}
