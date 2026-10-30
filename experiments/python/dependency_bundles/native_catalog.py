"""Lazy Python adapters over a process-lifetime, bounded Odin catalog."""
from collections.abc import Mapping,Set,Sequence


class LiveMap(Mapping):
    def __init__(self,reader):self.reader=reader
    def lookup(self,name,kind):
        if self.reader._closed:raise ValueError('native reader is closed')
        if not isinstance(name,str) or '\0' in name:return -1
        return self.reader._ffi.live_lookup(self.reader._handle,name,kind)


class LiveEntries(LiveMap):
    created=0
    def __len__(self):return self.reader.live_counts[0]
    def __iter__(self):
        for row in range(len(self)):yield self.reader.name(row)[0]
    def __contains__(self,name):return self.lookup(name,0)>=0
    def __getitem__(self,name):
        row=self.lookup(name,0)
        if row<0:raise KeyError(name)
        self.created+=1
        return self.reader.entry_type(name,row)


class LiveDirectories(LiveMap,Set):
    def __len__(self):return self.reader.live_counts[1]
    def __iter__(self):
        for i in range(len(self)):yield self.reader._ffi.live_dir_name(self.reader._handle,i)
    def __contains__(self,name):return self.lookup(name,2)>=0
    def __getitem__(self,name):
        row=self.lookup(name,2)
        if row<0:raise KeyError(name)
        return row


class LiveModules(LiveMap):
    def __len__(self):return self.reader.live_counts[2]
    def __iter__(self):
        for member in self.reader.entries:
            if member.endswith(('.py','.pyc')):
                stem=member[:-4] if member.endswith('.pyc') else member[:-3]
                if stem.endswith('/__init__'):stem=stem[:-len('/__init__')]
                yield stem.replace('/','.')
    def __getitem__(self,name):
        self.reader.module_queries+=1
        row=self.lookup(name,1)
        if row<0:raise KeyError(name)
        return self.reader.name(row)


class LivePackages(LiveMap):
    def __len__(self):return sum(1 for _ in self)
    def __iter__(self):
        for path in self.reader.directories:
            relative=path.rstrip('/')
            if self.get(relative) is not None:yield relative
    def __getitem__(self,relative):
        if not relative:return ''
        name=relative.replace('/','.')
        row=self.lookup(name,1)
        if row<0:raise KeyError(relative)
        member,package=self.reader.name(row)
        if not package or member.rsplit('/',1)[0]!=relative:raise KeyError(relative)
        return name


class LiveChildSequence(Sequence):
    def __init__(self,reader,path):
        self.reader,self.path=reader,path
        directory=reader.directories[path+'/' if path else '']
        self.head,self.count=reader._ffi.live_children(reader._handle,directory,1)
    def __len__(self):return self.count
    def __iter__(self):
        rows=[];row=self.head
        while row>=0:
            if len(rows)>=self.count:raise ValueError('invalid native child chain')
            member,package=self.reader.name(row)
            stem=member[:-4] if member.endswith('.pyc') else member[:-3]
            if package:stem=stem[:-len('/__init__')]
            child=stem.replace('/','.').rpartition('.')[2]
            if child!='__init__':rows.append((child,package))
            row=self.reader._ffi.live_next(self.reader._handle,row,1)
        if len(rows)!=self.count:raise ValueError('native child count differs')
        yield from sorted(rows)
    def __getitem__(self,index):return list(self)[index]
    def __contains__(self,item):
        child,package=item
        fullname=(self.path.replace('/','.')+'.' if self.path else '')+child
        row=self.reader.precomputed_modules.get(fullname)
        return row is not None and row[1]==package


class LiveChildren(LiveMap):
    def __len__(self):return len(self.reader.precomputed_packages)
    def __iter__(self):return iter(self.reader.precomputed_packages)
    def __getitem__(self,path):
        self.reader.precomputed_packages[path]
        return LiveChildSequence(self.reader,path)


class RootedMap(Mapping):
    def __init__(self,root,mapping):self.root,self.mapping=root,mapping
    def __len__(self):return len(self.mapping)
    def __iter__(self):
        for relative in self.mapping:yield self.root+('/'+relative if relative else '')
    def __getitem__(self,path):
        if path==self.root:return self.mapping['']
        if not isinstance(path,str) or not path.startswith(self.root+'/'):raise KeyError(path)
        return self.mapping[path[len(self.root)+1:]]


def resource_children(reader,prefix):
    relative=prefix.rstrip('/');directory=reader.directories[relative+'/' if relative else '']
    row,count=reader._ffi.live_children(reader._handle,directory,0);names=set();steps=0
    while row>=0:
        if steps>=count:raise ValueError('invalid native resource chain')
        steps+=1
        member,_=reader.name(row);names.add(member.rsplit('/',1)[-1])
        row=reader._ffi.live_next(reader._handle,row,0)
    if steps!=count:raise ValueError('native resource count differs')
    cursor=0
    while True:
        found=reader._ffi.live_subdir(reader._handle,directory,cursor)
        if found<0:break
        path=reader._ffi.live_dir_name(reader._handle,found)
        names.add(path[len(prefix):].rstrip('/'));cursor=found+1
    return sorted(names)
