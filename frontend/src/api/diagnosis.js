import request, { LLM_REQUEST_TIMEOUT_MS } from './request'

export function getInitialDiagnosisStatus(subject) {
  return request.get(
    `/diagnosis/initial/${encodeURIComponent(subject)}/status`,
  )
}

export function startInitialDiagnosis(subject, payload = {}) {
  return request.post(
    `/diagnosis/initial/${encodeURIComponent(subject)}/start`,
    payload,
    { timeout: LLM_REQUEST_TIMEOUT_MS },
  )
}

export function completeInitialDiagnosis(sessionId, answers) {
  return request.post(`/diagnosis/initial/${sessionId}/complete`, {
    answers,
  })
}

export function getDiagnosisSnapshots(subject) {
  return request.get(
    `/diagnosis/snapshots/${encodeURIComponent(subject)}`,
  )
}

export function recordSmartDiagnosis(subject, referenceId) {
  return request.post('/diagnosis/snapshots/smart', {
    subject,
    reference_id: referenceId,
  })
}
