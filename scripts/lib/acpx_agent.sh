#!/usr/bin/env bash

stok_acpx_env_value() {
  local role="$1"
  local key="$2"
  local default_value="$3"
  local role_var="CLOE_${role}_ACPX_${key}"
  local cloe_var="CLOE_ACPX_${key}"
  local openclaw_var="OPENCLAW_ACPX_${key}"

  if [[ -n "${role}" && -n "${!role_var:-}" ]]; then
    printf '%s\n' "${!role_var}"
  elif [[ -n "${!cloe_var:-}" ]]; then
    printf '%s\n' "${!cloe_var}"
  elif [[ -n "${!openclaw_var:-}" ]]; then
    printf '%s\n' "${!openclaw_var}"
  else
    printf '%s\n' "${default_value}"
  fi
}

stok_acpx_run_openclaw_task() {
  local root_dir="$1"
  local session_name="$2"
  local timeout_seconds="$3"
  local output_format="$4"
  local ttl_seconds="$5"
  local task="$6"

  acpx --cwd "${root_dir}" openclaw sessions ensure --name "${session_name}" >/dev/null
  if [[ -n "${ttl_seconds}" ]]; then
    acpx --cwd "${root_dir}" \
      --ttl "${ttl_seconds}" \
      --format "${output_format}" \
      --timeout "${timeout_seconds}" \
      openclaw -s "${session_name}" "${task}"
  else
    acpx --cwd "${root_dir}" \
      --format "${output_format}" \
      --timeout "${timeout_seconds}" \
      openclaw -s "${session_name}" "${task}"
  fi
}
