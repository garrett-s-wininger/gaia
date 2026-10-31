# frozen_string_literal: true
require 'digest'
module GaiaRubyPack
  class << self
    attr_reader :iseq_hits, :resolved, :fallbacks
    def install(path, pin, hash_provider: Digest::SHA256)
      raw = File.open(path, 'rb') do |file|
        size = file.stat.size
        raise 'pack file size' unless size.between?(16, 64 * 1024 * 1024)
        bytes = file.read(size + 1)
        raise 'pack file changed' unless bytes.bytesize == size
        bytes
      end
      raise 'pack size/header' unless raw.bytesize.between?(16, 64 * 1024 * 1024) && raw.byteslice(0, 8) == 'GAIARBI1'
      raise 'pack checksum' unless hash_provider.hexdigest(raw) == pin
      size = raw.byteslice(8, 8).unpack1('Q<')
      raise 'index bounds' unless size <= 8 * 1024 * 1024 && 16 + size <= raw.bytesize
      # Trusted, pinned interpreter-produced bytecode artifact. Never admit an
      # untrusted Marshal/ISeq merely because a header is structurally valid.
      index = Marshal.load(raw.byteslice(16, size))
      raise 'runtime/options mismatch' unless index[:version] == 1 && index[:ruby] == RUBY_DESCRIPTION &&
        index[:options] == RubyVM::InstructionSequence.compile_option
      raise 'entry bounds' unless index[:entries].length <= 20_000 && index[:entries].all? { |_, (offset, length)| offset >= 0 && length > 0 && 16 + size + offset + length <= raw.bytesize }
      @raw, @start, @entries, @catalog = raw.freeze, 16 + size, index[:entries], index[:catalog]
      @iseq_hits = @resolved = @fallbacks = 0
      @active_paths, @resolved_paths = [], {}
      RubyVM::InstructionSequence.singleton_class.prepend(InstructionSequenceHook)
      Kernel.prepend(RequireHook)
    end
    def iseq(path)
      row = @entries[path]
      return nil unless row
      @iseq_hits += 1
      RubyVM::InstructionSequence.load_from_binary(@raw.byteslice(@start + row[0], row[1]))
    end
    def resolve(feature)
      return nil unless feature.is_a?(String) && !feature.start_with?('/', '.')
      unless $LOAD_PATH == @active_paths
        @active_paths = $LOAD_PATH.map(&:dup)
        @resolved_paths.clear
        @active_catalog = {}
        $LOAD_PATH.each do |root|
          @active_catalog[root] = @catalog[root]
          unless @active_catalog[root]
            begin
              @active_catalog[root] = @catalog[File.realpath(root)]
            rescue SystemCallError
              @active_catalog[root] = nil
            end
          end
        end
      end
      if @resolved_paths.key?(feature)
        @resolved += 1 if @resolved_paths[feature]
        return @resolved_paths[feature]
      end
      $LOAD_PATH.each do |root|
        names = @active_catalog[root]
        # An unknown earlier directory could shadow a later indexed file.
        return nil unless names
        if (path = names[feature])
          @resolved += 1
          @resolved_paths[feature] = path
          return path
        end
      end
      @fallbacks += 1
      nil
    end
  end
  module InstructionSequenceHook
    def load_iseq(path)
      GaiaRubyPack.iseq(path.to_s)
    end
  end
  module RequireHook
    def require(feature)
      super(GaiaRubyPack.resolve(feature) || feature)
    end
    private :require
  end
end
provider = case ENV.fetch('GAIA_RUBY_SHA256_PROVIDER', 'digest')
when 'digest'
  Digest::SHA256
when 'openssl'
  require 'openssl'
  OpenSSL::Digest::SHA256
else
  raise 'unsupported SHA-256 provider'
end
GaiaRubyPack.install(ENV.fetch('GAIA_RUBY_PACK'), ENV.fetch('GAIA_RUBY_PACK_SHA256'), hash_provider: provider)
