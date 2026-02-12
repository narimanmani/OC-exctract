const form = document.getElementById('runner-form');
const statusEl = document.getElementById('status');
const runMetaEl = document.getElementById('run-meta');
const logsEl = document.getElementById('logs');
const artifactsEl = document.getElementById('artifacts');
const refreshBtn = document.getElementById('refresh-run');

const now = new Date();
const prior = new Date(now);
prior.setDate(now.getDate() - 30);
document.getElementById('start-date').value = prior.toISOString().slice(0, 10);
document.getElementById('end-date').value = now.toISOString().slice(0, 10);

let lastRunId = null;

function setStatus(message, isError = false) {
  statusEl.textContent = message;
  statusEl.style.color = isError ? '#fca5a5' : '#86efac';
}

function getConfig() {
  return {
    owner: document.getElementById('owner').value.trim(),
    repo: document.getElementById('repo').value.trim(),
    workflow: document.getElementById('workflow').value.trim(),
    ref: document.getElementById('ref').value.trim(),
    token: document.getElementById('token').value.trim(),
    startDate: document.getElementById('start-date').value,
    endDate: document.getElementById('end-date').value,
    environmentName: document.getElementById('environment-name').value.trim(),
  };
}

async function githubRequest(config, endpoint, options = {}) {
  const response = await fetch(`https://api.github.com${endpoint}`, {
    ...options,
    headers: {
      Accept: 'application/vnd.github+json',
      Authorization: `Bearer ${config.token}`,
      'X-GitHub-Api-Version': '2022-11-28',
      ...(options.headers || {}),
    },
  });

  if (!response.ok) {
    let details = response.statusText;
    try {
      const body = await response.json();
      details = body.message || details;
    } catch {
      // ignore json parse errors
    }
    throw new Error(`GitHub API ${response.status}: ${details}`);
  }
  return response;
}

async function resolveWorkflow(config) {
  const response = await githubRequest(config, `/repos/${config.owner}/${config.repo}/actions/workflows?per_page=100`);
  const data = await response.json();
  const workflows = data.workflows || [];
  const target = config.workflow.toLowerCase();

  const match = workflows.find((wf) => {
    if (!wf) return false;
    const candidates = [String(wf.id), wf.name, wf.path?.split('/').pop(), wf.path]
      .filter(Boolean)
      .map((v) => v.toLowerCase());
    return candidates.includes(target);
  });

  if (!match) {
    throw new Error(
      `Workflow '${config.workflow}' was not found. Confirm the workflow file exists in .github/workflows and that your token can read Actions metadata.`,
    );
  }

  return match;
}

async function getRepo(config) {
  const response = await githubRequest(config, `/repos/${config.owner}/${config.repo}`);
  return response.json();
}

async function getLatestRun(config, workflowId) {
  const response = await githubRequest(
    config,
    `/repos/${config.owner}/${config.repo}/actions/workflows/${workflowId}/runs?per_page=5`,
  );
  const data = await response.json();
  return data.workflow_runs?.[0] || null;
}

function renderRunMeta(run) {
  if (!run) {
    runMetaEl.innerHTML = '<p>No runs found for this workflow.</p>';
    return;
  }

  const started = run.run_started_at || run.created_at;
  runMetaEl.innerHTML = `
    <p><strong>Run #${run.run_number}</strong> (${run.status}/${run.conclusion ?? 'in progress'})</p>
    <p><strong>Branch:</strong> ${run.head_branch}</p>
    <p><strong>Started:</strong> ${started ?? 'unknown'}</p>
    <p><a href="${run.html_url}" target="_blank" rel="noreferrer">Open run in GitHub</a></p>
  `;
}

async function renderLogs(config, runId) {
  logsEl.textContent = 'Loading logs ...';
  const jobsResponse = await githubRequest(
    config,
    `/repos/${config.owner}/${config.repo}/actions/runs/${runId}/jobs?per_page=10`,
  );
  const jobsData = await jobsResponse.json();
  const firstJob = jobsData.jobs?.[0];

  if (!firstJob) {
    logsEl.textContent = 'No jobs found for this run yet.';
    return;
  }

  logsEl.textContent = [
    'GitHub returns job logs as a compressed download from the browser API.',
    'Open the run in GitHub to stream logs live, or use artifacts once available.',
    `Run URL: ${firstJob.html_url}`,
  ].join('\n');
}

async function downloadArtifact(config, artifact) {
  setStatus(`Downloading artifact ${artifact.name}...`);
  const response = await githubRequest(config, `/repos/${config.owner}/${config.repo}/actions/artifacts/${artifact.id}/zip`);
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = `${artifact.name}.zip`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
  setStatus(`Artifact ${artifact.name} downloaded.`);
}

async function renderArtifacts(config, runId) {
  const response = await githubRequest(
    config,
    `/repos/${config.owner}/${config.repo}/actions/runs/${runId}/artifacts`,
  );
  const data = await response.json();
  const artifacts = data.artifacts || [];

  if (!artifacts.length) {
    artifactsEl.innerHTML = '<li>No artifacts available yet.</li>';
    return;
  }

  artifactsEl.innerHTML = '';
  for (const artifact of artifacts) {
    const li = document.createElement('li');
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.textContent = `Download ${artifact.name}`;
    btn.addEventListener('click', () => {
      downloadArtifact(config, artifact).catch((error) => setStatus(error.message, true));
    });

    const meta = document.createElement('small');
    meta.textContent = ` (${artifact.size_in_bytes} bytes, expires ${artifact.expires_at})`;

    li.appendChild(btn);
    li.appendChild(meta);
    artifactsEl.appendChild(li);
  }
}

async function validateConfig(config) {
  const [repoData, workflow] = await Promise.all([getRepo(config), resolveWorkflow(config)]);

  if (!config.ref) {
    const refInput = document.getElementById('ref');
    refInput.value = repoData.default_branch;
    config.ref = repoData.default_branch;
  }

  return { repoData, workflow };
}

async function refreshLatestRun() {
  const config = getConfig();
  if (!config.owner || !config.repo || !config.workflow || !config.token) {
    setStatus('Owner, repo, workflow, and token are required.', true);
    return;
  }

  setStatus('Fetching latest run...');
  const { workflow } = await validateConfig(config);
  const run = await getLatestRun(config, workflow.id);
  renderRunMeta(run);

  if (!run) {
    logsEl.textContent = 'No logs yet.';
    artifactsEl.innerHTML = '<li>No artifacts yet.</li>';
    return;
  }

  lastRunId = run.id;
  await renderLogs(config, run.id);
  await renderArtifacts(config, run.id);
  setStatus(`Latest run loaded (run #${run.run_number}).`);
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const config = getConfig();

  try {
    setStatus('Validating repository and workflow...');
    const { repoData, workflow } = await validateConfig(config);

    if (!config.ref) {
      config.ref = repoData.default_branch;
    }

    setStatus('Dispatching workflow...');
    await githubRequest(config, `/repos/${config.owner}/${config.repo}/actions/workflows/${workflow.id}/dispatches`, {
      method: 'POST',
      body: JSON.stringify({
        ref: config.ref,
        inputs: {
          start_date: config.startDate,
          end_date: config.endDate,
          environment_name: config.environmentName || 'OC',
        },
      }),
    });

    setStatus('Workflow dispatched. Waiting for run to appear...');
    const startedAt = Date.now();
    let run = null;
    while (Date.now() - startedAt < 90000) {
      run = await getLatestRun(config, workflow.id);
      if (run && run.id !== lastRunId) {
        break;
      }
      await new Promise((resolve) => setTimeout(resolve, 5000));
    }

    if (!run) {
      throw new Error('Workflow was dispatched, but no new run appeared within 90 seconds. Verify the selected ref and open Actions in GitHub.');
    }

    lastRunId = run.id;
    renderRunMeta(run);
    await renderLogs(config, run.id);
    await renderArtifacts(config, run.id);
    setStatus(`Run #${run.run_number} started. Use Refresh to see updates.`);
  } catch (error) {
    setStatus(error.message, true);
  }
});

refreshBtn.addEventListener('click', () => {
  refreshLatestRun().catch((error) => setStatus(error.message, true));
});
