const frame = document.getElementById('office-frame')
const error = document.getElementById('office-error')

function showError() {
  frame.hidden = true
  error.hidden = false
}

try {
  const config = JSON.parse(document.getElementById('office-config').textContent)
  config.events = { onError: showError }
  new window.DocsAPI.DocEditor('office-frame', config)
} catch {
  showError()
}
