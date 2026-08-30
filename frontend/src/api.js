export async function analyzeContour(file) {
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch("/api/analyzeContour", {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }

  return res.json();
}
