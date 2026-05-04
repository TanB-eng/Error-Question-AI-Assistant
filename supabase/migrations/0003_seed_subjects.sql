insert into public.subjects (id, code, name, sort_order) values
  (1, 'math', '数学', 1),
  (2, 'physics', '物理', 2),
  (3, 'chemistry', '化学', 3),
  (4, 'biology', '生物', 4),
  (5, 'chinese', '语文', 5),
  (6, 'english', '英语', 6),
  (7, 'history', '历史', 7),
  (8, 'geography', '地理', 8),
  (9, 'politics', '政治', 9),
  (10, 'specialized', '专业课', 10)
on conflict (id) do update
set
  code = excluded.code,
  name = excluded.name,
  sort_order = excluded.sort_order;
