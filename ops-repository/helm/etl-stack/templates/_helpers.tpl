{{- define "etl-stack.name" -}}
{{- .Chart.Name }}
{{- end }}

{{- define "etl-stack.labels" -}}
app.kubernetes.io/name: {{ include "etl-stack.name" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}
