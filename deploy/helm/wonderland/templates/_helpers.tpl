{{- define "wonderland.image" -}}
{{- $image := index .root.Values.images .service -}}
{{- if not (regexMatch "^[a-zA-Z0-9./:_-]+@sha256:[a-f0-9]{64}$" $image) -}}
{{- fail (printf "images.%s must be an immutable repository@sha256:digest reference" .service) -}}
{{- end -}}
{{- $image -}}
{{- end -}}

{{- define "wonderland.security" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop: [ALL]
{{- end -}}
