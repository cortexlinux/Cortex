/**
 * @file config.cpp
 * @brief Configuration implementation with YAML support (PR 1: Core Daemon)
 */

#include "cortexd/config.h"
#include "cortexd/logger.h"
#include <fstream>
#include <sstream>
#include <yaml-cpp/yaml.h>

namespace cortexd {

std::optional<Config> Config::load(const std::string& path) {
    try {
        std::string expanded_path = expand_path(path);
        
        // Check if file exists
        std::ifstream file(expanded_path);
        if (!file.good()) {
            LOG_WARN("Config", "Configuration file not found: " + expanded_path);
            return std::nullopt;
        }
        
        YAML::Node yaml = YAML::LoadFile(expanded_path);
        Config config;
        
        // Socket configuration
        if (yaml["socket"]) {
            auto socket = yaml["socket"];
            if (socket["path"]) config.socket_path = socket["path"].as<std::string>();
            if (socket["backlog"]) config.socket_backlog = socket["backlog"].as<int>();
            if (socket["timeout_ms"]) config.socket_timeout_ms = socket["timeout_ms"].as<int>();
        }
        
        // Rate limiting
        if (yaml["rate_limit"]) {
            auto rate = yaml["rate_limit"];
            if (rate["max_requests_per_sec"]) config.max_requests_per_sec = rate["max_requests_per_sec"].as<int>();
        }
        
        // Logging
        if (yaml["log_level"]) {
            config.log_level = yaml["log_level"].as<int>();
        }
        
        // Monitoring thresholds
        if (yaml["monitoring"]) {
            auto monitoring = yaml["monitoring"];
            if (monitoring["cpu"]) {
                auto cpu = monitoring["cpu"];
                if (cpu["warning_threshold"]) {
                    config.cpu_warning_threshold = cpu["warning_threshold"].as<double>();
                }
                if (cpu["critical_threshold"]) {
                    config.cpu_critical_threshold = cpu["critical_threshold"].as<double>();
                }
            }
            if (monitoring["memory"]) {
                auto memory = monitoring["memory"];
                if (memory["warning_threshold"]) {
                    config.memory_warning_threshold = memory["warning_threshold"].as<double>();
                }
                if (memory["critical_threshold"]) {
                    config.memory_critical_threshold = memory["critical_threshold"].as<double>();
                }
            }
            if (monitoring["disk"]) {
                auto disk = monitoring["disk"];
                if (disk["warning_threshold"]) {
                    config.disk_warning_threshold = disk["warning_threshold"].as<double>();
                }
                if (disk["critical_threshold"]) {
                    config.disk_critical_threshold = disk["critical_threshold"].as<double>();
                }
            }
            if (monitoring["check_interval_seconds"]) {
                config.monitor_check_interval_seconds = monitoring["check_interval_seconds"].as<int>();
            }
        }
        
        // Expand paths and validate
        config.expand_paths();
        std::string error = config.validate();
        if (!error.empty()) {
            LOG_ERROR("Config", "Configuration validation failed: " + error);
            return std::nullopt;
        }
        
        LOG_INFO("Config", "Configuration loaded from " + expanded_path);
        return config;
        
    } catch (const YAML::Exception& e) {
        LOG_ERROR("Config", "YAML parse error: " + std::string(e.what()));
        return std::nullopt;
    } catch (const std::exception& e) {
        LOG_ERROR("Config", "Error loading config: " + std::string(e.what()));
        return std::nullopt;
    }
}

bool Config::save(const std::string& path) const {
    try {
        std::string expanded_path = expand_path(path);
        
        YAML::Emitter out;
        out << YAML::BeginMap;
        
        // Socket
        out << YAML::Key << "socket" << YAML::Value << YAML::BeginMap;
        out << YAML::Key << "path" << YAML::Value << socket_path;
        out << YAML::Key << "backlog" << YAML::Value << socket_backlog;
        out << YAML::Key << "timeout_ms" << YAML::Value << socket_timeout_ms;
        out << YAML::EndMap;
        
        // Rate limiting
        out << YAML::Key << "rate_limit" << YAML::Value << YAML::BeginMap;
        out << YAML::Key << "max_requests_per_sec" << YAML::Value << max_requests_per_sec;
        out << YAML::EndMap;
        
        // Logging
        out << YAML::Key << "log_level" << YAML::Value << log_level;
        
        // Monitoring thresholds
        out << YAML::Key << "monitoring" << YAML::Value << YAML::BeginMap;
        out << YAML::Key << "cpu" << YAML::Value << YAML::BeginMap;
        out << YAML::Key << "warning_threshold" << YAML::Value << cpu_warning_threshold;
        out << YAML::Key << "critical_threshold" << YAML::Value << cpu_critical_threshold;
        out << YAML::EndMap;
        out << YAML::Key << "memory" << YAML::Value << YAML::BeginMap;
        out << YAML::Key << "warning_threshold" << YAML::Value << memory_warning_threshold;
        out << YAML::Key << "critical_threshold" << YAML::Value << memory_critical_threshold;
        out << YAML::EndMap;
        out << YAML::Key << "disk" << YAML::Value << YAML::BeginMap;
        out << YAML::Key << "warning_threshold" << YAML::Value << disk_warning_threshold;
        out << YAML::Key << "critical_threshold" << YAML::Value << disk_critical_threshold;
        out << YAML::EndMap;
        out << YAML::Key << "check_interval_seconds" << YAML::Value << monitor_check_interval_seconds;
        out << YAML::EndMap;
        
        out << YAML::EndMap;
        
        std::ofstream file(expanded_path);
        if (!file.good()) {
            LOG_ERROR("Config", "Cannot write to " + expanded_path);
            return false;
        }
        
        file << out.c_str();
        LOG_INFO("Config", "Configuration saved to " + expanded_path);
        return true;
        
    } catch (const std::exception& e) {
        LOG_ERROR("Config", "Error saving config: " + std::string(e.what()));
        return false;
    }
}

void Config::expand_paths() {
    socket_path = expand_path(socket_path);
}

std::string Config::validate() const {
    if (socket_backlog <= 0) {
        return "socket_backlog must be positive";
    }
    if (socket_timeout_ms <= 0) {
        return "socket_timeout_ms must be positive";
    }
    if (max_requests_per_sec <= 0) {
        return "max_requests_per_sec must be positive";
    }
    if (log_level < 0 || log_level > 4) {
        return "log_level must be between 0 and 4";
    }
    if (cpu_warning_threshold < 0 || cpu_warning_threshold > 100 ||
        cpu_critical_threshold < 0 || cpu_critical_threshold > 100) {
        return "CPU thresholds must be between 0 and 100";
    }
    if (cpu_warning_threshold >= cpu_critical_threshold) {
        return "CPU warning threshold must be less than critical threshold";
    }
    if (memory_warning_threshold < 0 || memory_warning_threshold > 100 ||
        memory_critical_threshold < 0 || memory_critical_threshold > 100) {
        return "Memory thresholds must be between 0 and 100";
    }
    if (memory_warning_threshold >= memory_critical_threshold) {
        return "Memory warning threshold must be less than critical threshold";
    }
    if (disk_warning_threshold < 0 || disk_warning_threshold > 100 ||
        disk_critical_threshold < 0 || disk_critical_threshold > 100) {
        return "Disk thresholds must be between 0 and 100";
    }
    if (disk_warning_threshold >= disk_critical_threshold) {
        return "Disk warning threshold must be less than critical threshold";
    }
    if (monitor_check_interval_seconds <= 0) {
        return "monitor_check_interval_seconds must be positive";
    }
    return "";  // Valid
}

Config Config::defaults() {
    return Config{};
}

// ConfigManager implementation

ConfigManager& ConfigManager::instance() {
    static ConfigManager instance;
    return instance;
}

bool ConfigManager::load(const std::string& path) {
    Config config_copy;
    std::vector<ChangeCallback> callbacks_copy;
    
    {
        std::lock_guard<std::mutex> lock(mutex_);
        
        auto loaded = Config::load(path);
        if (!loaded) {
            LOG_WARN("ConfigManager", "Using default configuration");
            config_ = Config::defaults();
            config_.expand_paths();
            return false;
        }
        
        config_ = *loaded;
        config_path_ = path;
        
        // Copy for callback invocation outside the lock
        config_copy = config_;
        callbacks_copy = callbacks_;
    }
    
    // Invoke callbacks outside the lock to prevent deadlock
    notify_callbacks_unlocked(callbacks_copy, config_copy);
    return true;
}

bool ConfigManager::reload() {
    std::string path_copy;
    Config config_copy;
    std::vector<ChangeCallback> callbacks_copy;
    
    {
        std::lock_guard<std::mutex> lock(mutex_);
        
        // Copy config_path_ while holding mutex to avoid TOCTOU race
        if (config_path_.empty()) {
            LOG_WARN("ConfigManager", "No config path set, cannot reload");
            return false;
        }
        path_copy = config_path_;
    }
    
    // Load config outside the lock (Config::load is self-contained)
    auto loaded = Config::load(path_copy);
    if (!loaded) {
        LOG_ERROR("ConfigManager", "Failed to reload configuration");
        return false;
    }
    
    {
        std::lock_guard<std::mutex> lock(mutex_);
        if (config_path_ != path_copy) {
            LOG_WARN("ConfigManager", "Config path changed during reload; aborting");
            return false;
        }
        config_ = *loaded;
        
        // Copy for callback invocation outside the lock
        config_copy = config_;
        callbacks_copy = callbacks_;
    }
    
    // Invoke callbacks outside the lock to prevent deadlock
    notify_callbacks_unlocked(callbacks_copy, config_copy);
    LOG_INFO("ConfigManager", "Configuration reloaded");
    return true;
}

Config ConfigManager::get() const {
    std::lock_guard<std::mutex> lock(mutex_);
    return config_;  // Return copy for thread safety
}

void ConfigManager::on_change(ChangeCallback callback) {
    std::lock_guard<std::mutex> lock(mutex_);
    callbacks_.push_back(std::move(callback));
}

void ConfigManager::notify_callbacks() {
    // This method should only be called while NOT holding the mutex
    // For internal use, prefer notify_callbacks_unlocked
    Config config_copy;
    std::vector<ChangeCallback> callbacks_copy;
    
    {
        std::lock_guard<std::mutex> lock(mutex_);
        config_copy = config_;
        callbacks_copy = callbacks_;
    }
    
    notify_callbacks_unlocked(callbacks_copy, config_copy);
}

void ConfigManager::notify_callbacks_unlocked(
    const std::vector<ChangeCallback>& callbacks,
    const Config& config) {
    // Invoke callbacks outside the lock to prevent deadlock if a callback
    // calls ConfigManager::get() or other mutex-guarded methods
    for (const auto& callback : callbacks) {
        try {
            callback(config);
        } catch (const std::exception& e) {
            LOG_ERROR("ConfigManager", "Callback error: " + std::string(e.what()));
        }
    }
}

} // namespace cortexd
