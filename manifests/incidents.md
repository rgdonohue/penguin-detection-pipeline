# Pipeline Incidents Log

Track failures, rollbacks, and lessons learned. Part of DORA Change Failure Rate tracking.

---

## Incident Template

```markdown
### [YYYY-MM-DD] Brief Description

**Severity:** [Low/Medium/High/Critical]
**Stage:** [harvest/lidar/thermal/fusion]
**Impact:** What broke? Data loss? Invalid outputs?
**Root Cause:** Why did it happen?
**Resolution:** What fixed it?
**Rollback Required:** [Yes/No] - If yes, to which commit?
**Time to Restore:** [minutes/hours]
**Prevention:** What changes prevent recurrence?
```

---

## Log

### [2025-10-08] Initial Setup - No Incidents

Pipeline established with golden AOI test. LiDAR detector validated on cloud3.las (879 detections).

**Lead Time:** ~4 hours from PRD creation to working LiDAR test
**Change Failure Rate:** 0% (1/1 tests passed)
**Deployment Frequency:** Initial setup
**Time to Restore:** N/A

---

<!-- Future incidents go below -->
