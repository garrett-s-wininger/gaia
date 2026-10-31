# frozen_string_literal: true
require 'json'
require 'digest'
require 'rubocop'

output = File.expand_path(ARGV.fetch(0))
# Discovery/precompilation only: no RuboCop inspection or result is executed.
roots = $LOAD_PATH.map { |root| File.expand_path(root) }.uniq
entries = {}
catalog = {}
payload = +''.b
failures = []
sources = {}
roots.each do |root|
  names = {}
  Dir.glob(File.join(root, '**', '*.{rb,so,bundle}')).sort.each do |path|
    relative = path.delete_prefix(root + '/')
    extension = File.extname(path)
    feature = relative.delete_suffix(extension)
    names[feature] ||= path
    names[relative] = path
    next unless extension == '.rb' && !entries.key?(path)
    begin
      binary = RubyVM::InstructionSequence.compile_file(path).to_binary
      entries[path] = [payload.bytesize, binary.bytesize]
      payload << binary
      sources[path] = Digest::SHA256.file(path).hexdigest
    rescue SyntaxError, TypeError => e
      failures << [path, e.class.name]
    end
  end
  catalog[root] = names
end
index = Marshal.dump({version: 1, ruby: RUBY_DESCRIPTION, options: RubyVM::InstructionSequence.compile_option,
  catalog: catalog, entries: entries})
File.binwrite(output, "GAIARBI1" + [index.bytesize].pack('Q<') + index + payload)
File.write(output + '.json', JSON.pretty_generate({sha256: Digest::SHA256.file(output).hexdigest,
  bytes: File.size(output), index_bytes: index.bytesize, files: entries.length, roots: roots.length,
  ruby: RUBY_DESCRIPTION, options: RubyVM::InstructionSequence.compile_option, failures: failures,
  source_sha256: sources, gems: Gem.loaded_specs.transform_values { |spec| spec.version.to_s }}) + "\n")
