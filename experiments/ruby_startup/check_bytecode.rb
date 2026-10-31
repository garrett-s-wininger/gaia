# frozen_string_literal: true
require 'json'
require 'openssl'
require 'bootsnap'
root = File.expand_path(ARGV.fetch(0))
manifest = JSON.parse(File.read(File.join(root, 'results.json')))
pack = File.binread(File.join(root, 'work/code.pack'))
raise 'pack checksum' unless OpenSSL::Digest::SHA256.hexdigest(pack) == manifest.fetch('producer').fetch('sha256')
length = pack.byteslice(8, 8).unpack1('Q<')
index = Marshal.load(pack.byteslice(16, length))
raise 'options mismatch' unless index.fetch(:options) == RubyVM::InstructionSequence.compile_option
Bootsnap.setup(cache_dir: File.join(root, 'work/bootsnap-cache'), development_mode: false,
  load_path_cache: true, compile_cache_iseq: true, compile_cache_yaml: true)
gem_root = Gem::Specification.find_by_name('rubocop', '=1.92.2').full_gem_path
values = %w[lib/rubocop/version.rb lib/rubocop/cop/base.rb lib/rubocop/runner.rb].map do |relative|
  path = File.join(gem_root, relative)
  offset, size = index.fetch(:entries).fetch(path)
  binary = pack.byteslice(16 + length + offset, size)
  direct = RubyVM::InstructionSequence.compile_file(path)
  cached = Bootsnap::CompileCache::ISeq.fetch(path)
  packed = RubyVM::InstructionSequence.load_from_binary(binary)
  raise 'instruction trees differ' unless direct.to_a == cached.to_a && direct.to_a == packed.to_a
  {file: relative, bytes: size, trees_equal: true,
    direct_sha256: OpenSSL::Digest::SHA256.hexdigest(direct.to_binary),
    bootsnap_roundtrip_sha256: OpenSSL::Digest::SHA256.hexdigest(cached.to_binary),
    packed_sha256: OpenSSL::Digest::SHA256.hexdigest(binary)}
end
puts JSON.pretty_generate({ruby: RUBY_DESCRIPTION, options: RubyVM::InstructionSequence.compile_option,
  files: values, all_instruction_trees_equal: true})
