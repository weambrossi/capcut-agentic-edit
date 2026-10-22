async function request(method, url, body) {
  const res = await fetch(url, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status}).`);
  return data;
}

export const api = {
  skills: () => request('GET', '/api/skills'),
  createStyle: (body) => request('POST', '/api/styles', body),
  saveSection: (id, body) => request('PUT', `/api/skills/${id}/section`, body),
  saveSource: (id, body) => request('PUT', `/api/skills/${id}/source`, body),
  history: (id) => request('GET', `/api/skills/${id}/history`),
  revision: (id, hash) => request('GET', `/api/skills/${id}/history/${hash}`),
  references: () => request('GET', '/api/references'),
  updateReference: (id, body) => request('PATCH', `/api/references/${id}`, body),
  deleteReference: (id) => request('DELETE', `/api/references/${id}`),
  videoUrl: (id) => `/api/references/${id}/file`,
  thumbUrl: (id) => `/api/references/${id}/thumb`,

  /** Streams the file as the request body; XHR because fetch has no upload progress. */
  upload(file, { name, notes, styles }, onProgress) {
    const q = new URLSearchParams({ filename: file.name, name, notes, styles: styles.join(',') });
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      xhr.open('POST', `/api/references?${q}`);
      xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
      xhr.onload = () => {
        let data = {};
        try { data = JSON.parse(xhr.responseText); } catch { /* not JSON */ }
        if (xhr.status >= 200 && xhr.status < 300) resolve(data);
        else reject(new Error(data.error || `Upload failed (${xhr.status}).`));
      };
      xhr.onerror = () => reject(new Error('Upload failed. Is the dashboard server still running?'));
      xhr.send(file);
    });
  },
};

export const formatBytes = (n) => (n >= 1024 ** 3 ? `${(n / 1024 ** 3).toFixed(1)} GB` : `${(n / 1024 ** 2).toFixed(1)} MB`);
export const formatDuration = (s) => `${Math.floor(s / 60)}:${String(Math.round(s % 60)).padStart(2, '0')}`;
export const formatDate = (iso) => new Date(iso).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });
