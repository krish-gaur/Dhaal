import type { ClauseStatus } from "./api";

/**
 * A value that cannot be rendered without the status of the evidence
 * behind it (F-UI8). Money components accept only WithStatus amounts,
 * so a bare number is a compile-time error.
 */
export interface WithStatus<T> {
  value: T;
  status: ClauseStatus;
}

export function withStatus<T>(value: T, status: ClauseStatus): WithStatus<T> {
  return { value, status };
}
