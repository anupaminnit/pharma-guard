import { motion } from "framer-motion";

const statusConfig = {
  info:    { color: "#4a90d9", prefix: "ℹ" },
  running: { color: "#f5a623", prefix: "⟳" },
  success: { color: "#00e5a0", prefix: "✓" },
  warning: { color: "#f5a623", prefix: "⚠" },
  error:   { color: "#ff4444", prefix: "✗" },
};

export default function AgentLog({ log, mini = false }) {
  if (!log || log.length === 0) {
    return (
      <div className="log-empty">
        {mini ? "Initializing agents..." : "No agent activity yet"}
      </div>
    );
  }

  return (
    <div className={`agent-log ${mini ? "mini" : ""}`}>
      {log.map((entry, i) => {
        const cfg = statusConfig[entry.status] || statusConfig.info;
        return (
          <motion.div
            key={i}
            className="log-entry"
            style={{ "--log-color": cfg.color }}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: i * 0.06 }}
          >
            <span className="log-prefix">{cfg.prefix}</span>
            <div className="log-body">
              <div className="log-agent-step">
                <span className="log-agent">{entry.agent}</span>
                <span className="log-divider">›</span>
                <span className="log-step">{entry.step}</span>
              </div>
              {entry.detail && (
                <div className="log-detail">{entry.detail}</div>
              )}
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
