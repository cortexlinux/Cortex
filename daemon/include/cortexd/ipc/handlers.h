/**
 * @file handlers.h
 * @brief IPC request handlers
 */

#pragma once

#include "cortexd/ipc/server.h"
#include "cortexd/ipc/protocol.h"
#include <memory>

namespace cortexd {

// Forward declarations
class SystemMonitor;
class AlertManager;

/**
 * @brief IPC request handlers
 */
class Handlers {
public:
    /**
     * @brief Register all handlers with IPC server
     * @param server IPC server instance
     * @param monitor System monitor instance (optional, for status/health handlers)
     * @param alerts Alert manager instance (optional, for alert handlers)
     */
    static void register_all(
        IPCServer& server,
        SystemMonitor* monitor = nullptr,
        std::shared_ptr<AlertManager> alerts = nullptr
    );
    
private:
    // Handler implementations
    static Response handle_ping(const Request& req);
    static Response handle_version(const Request& req);
    
    // Config handlers
    static Response handle_config_get(const Request& req);
    static Response handle_config_reload(const Request& req);
    
    // Daemon control
    static Response handle_shutdown(const Request& req);
    
    // Monitoring handlers
    static Response handle_health(const Request& req, SystemMonitor* monitor);
    
    // Alert handlers
    static Response handle_alerts_get(const Request& req, std::shared_ptr<AlertManager> alerts);
    static Response handle_alerts_acknowledge(const Request& req, std::shared_ptr<AlertManager> alerts);
    static Response handle_alerts_dismiss(const Request& req, std::shared_ptr<AlertManager> alerts);
};

} // namespace cortexd