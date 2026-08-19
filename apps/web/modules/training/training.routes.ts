export const trainingRoutes = {
  listJobs: "GET /api/training/jobs",
  createJob: "POST /api/training/jobs",
  getJobDetails: "GET /api/training/jobs/:jobId",
  cancelJob: "POST /api/training/jobs/:jobId/cancel",
  viewLogs: "GET /api/training/jobs/:jobId/logs",
} as const;
