; Hand-checked extraction cases, deliberately including unreachable blocks.
define i32 @diamond(i1 %condition, i32 %a, i32 %b) {
entry:
  br i1 %condition, label %left, label %right
left:
  %x = add i32 %a, 1
  br label %join
right:
  br label %join
join:
  %p = phi i32 [ %x, %left ], [ %b, %right ]
  %result = add i32 %p, 1
  ret i32 %result
}

define i32 @loop(i32 %n, i32 %a) {
entry:
  br label %body
body:
  %i = phi i32 [ 0, %entry ], [ %next, %body ]
  %sum = add i32 %i, %a
  %next = add i32 %i, 1
  %condition = icmp slt i32 %next, %n
  br i1 %condition, label %body, label %exit
exit:
  ret i32 %sum
}

define i32 @unreachable_blocks(i32 %a) {
entry:
  ret i32 %a
dead1:
  %x = add i32 %a, 1
  br label %dead2
dead2:
  ret i32 %x
}

define void @self_phi(i32 %a) {
entry:
  br label %body
body:
  %p = phi i32 [ %a, %entry ], [ %p, %body ]
  br label %body
}

define void @empty_values() {
entry:
  ret void
}

declare i32 @may_throw()
declare i32 @personality(...)
define i32 @invoke_edge(i32 %a) personality ptr @personality {
entry:
  %value = invoke i32 @may_throw() to label %normal unwind label %exception
normal:
  %p = phi i32 [ %value, %entry ]
  %sum = add i32 %p, %a
  ret i32 %sum
exception:
  %landing = landingpad { ptr, i32 } cleanup
  ret i32 %a
}
