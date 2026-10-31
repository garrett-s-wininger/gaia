# frozen_string_literal: true
# Every mode shares lifecycle/identity observation and the real upstream CLI.
require 'json'
mode = ENV.fetch('GAIA_RUBY_MODE')
if mode == 'bootsnap'
  require 'bootsnap'
  Bootsnap.setup(cache_dir: ENV.fetch('GAIA_BOOTSNAP_CACHE'), development_mode: false,
    load_path_cache: true, compile_cache_iseq: true, compile_cache_yaml: true)
elsif mode.start_with?('packed')
  require_relative 'packed_loader'
end
at_exit do
  status = $!.is_a?(SystemExit) ? $!.status : ($! ? 2 : 0)
  rss = File.read('/proc/self/status')[/^VmHWM:\s+(\d+)/, 1].to_i * 1024
  pack = defined?(GaiaRubyPack) ? {iseq_hits: GaiaRubyPack.iseq_hits, resolved: GaiaRubyPack.resolved, fallbacks: GaiaRubyPack.fallbacks} : nil
  File.write(ENV.fetch('GAIA_EXIT_MARKER'), JSON.generate({status: status, token: ENV.fetch('GAIA_REQUEST_TOKEN'),
    cwd: Dir.pwd, crypto: (defined?(OpenSSL) ? {version: OpenSSL::VERSION, library: OpenSSL::OPENSSL_LIBRARY_VERSION} : nil), ruby: RUBY_DESCRIPTION, rss_peak_bytes: rss, pack: pack,
    gems: Gem.loaded_specs.transform_values { |spec| spec.version.to_s }, features: $LOADED_FEATURES.sort}))
end
