import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import json
import os

class MapEditor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("地圖編輯器")
        self.geometry("1200x800")

        self.maps_data = self.load_maps_data()
        self.current_map_id = None

        self.detail_widgets = {}

        self.create_widgets()
        self.populate_maps_list()

    def load_maps_data(self):
        # Employee version always starts with a blank slate.
        return {}

    def export_json_for_pasting(self):
        if not self.maps_data:
            messagebox.showwarning("警告", "沒有地圖資料可以匯出。")
            return

        json_string = json.dumps(self.maps_data, ensure_ascii=False, indent=2)

        export_window = tk.Toplevel(self)
        export_window.title("匯出的JSON資料")
        export_window.geometry("600x500")

        ttk.Label(export_window, text="請複製以下所有文字 (Ctrl+A, Ctrl+C):").pack(pady=5)

        text_widget = tk.Text(export_window, wrap="word")
        text_widget.pack(fill="both", expand=True, padx=10, pady=5)
        text_widget.insert("1.0", json_string)
        text_widget.config(state="normal")

        ttk.Button(export_window, text="關閉", command=export_window.destroy).pack(pady=5)
        export_window.transient(self)
        export_window.grab_set()
        self.wait_window(export_window)
    
    def save_maps_data(self):
        try:
            with open(os.path.join('cogs', 'maps_data.json'), 'w', encoding='utf-8') as f:
                json.dump(self.maps_data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("成功", "地圖資料儲存成功。")
        except Exception as e:
            messagebox.showerror("錯誤", f"儲存地圖資料失敗: {e}")

    def create_widgets(self):
        left_frame = ttk.Frame(self, width=250)
        left_frame.pack(side="left", fill="y", padx=10, pady=10)
        left_frame.pack_propagate(False)

        right_frame = ttk.Frame(self)
        right_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        maps_list_frame = ttk.LabelFrame(left_frame, text="地圖")
        maps_list_frame.pack(fill="both", expand=True)

        self.maps_tree = ttk.Treeview(maps_list_frame, show="tree", selectmode="browse")
        self.maps_tree.pack(side="left", fill="both", expand=True)
        
        maps_scrollbar = ttk.Scrollbar(maps_list_frame, orient="vertical", command=self.maps_tree.yview)
        maps_scrollbar.pack(side="right", fill="y")
        self.maps_tree.configure(yscrollcommand=maps_scrollbar.set)
        self.maps_tree.bind("<<TreeviewSelect>>", self.on_map_select)

        map_buttons_frame = ttk.Frame(left_frame)
        map_buttons_frame.pack(fill="x", pady=5)

        ttk.Button(map_buttons_frame, text="讀取選擇", command=self.load_selected_map).pack(fill="x")
        ttk.Button(map_buttons_frame, text="建立新地圖", command=self.create_new_map).pack(fill="x")
        ttk.Button(map_buttons_frame, text="儲存當前地圖", command=self.save_current_map).pack(fill="x")
        ttk.Button(map_buttons_frame, text="刪除選擇", command=self.delete_selected_map).pack(fill="x")
        ttk.Button(map_buttons_frame, text="匯出JSON以供複製", command=self.export_json_for_pasting).pack(fill="x", pady=(10,0))

        self.details_notebook = ttk.Notebook(right_frame)
        self.details_notebook.pack(fill="both", expand=True)

        self.tab_main = ttk.Frame(self.details_notebook)
        self.tab_layout = ttk.Frame(self.details_notebook)
        self.tab_entities = ttk.Frame(self.details_notebook)

        self.details_notebook.add(self.tab_main, text="主要資訊")
        self.details_notebook.add(self.tab_layout, text="佈局與圖例")
        self.details_notebook.add(self.tab_entities, text="怪物、獎勵、出口")

        ttk.Label(self.tab_main, text="請選擇一個地圖並點擊 '讀取選擇' 來查看詳細資訊。").pack(pady=20)

    def populate_maps_list(self):
        for i in self.maps_tree.get_children(): self.maps_tree.delete(i)
        dungeons, standalone_maps = {}, []
        for map_id, details in self.maps_data.items():
            dungeon_id = details.get("dungeon_id")
            if dungeon_id:
                if dungeon_id not in dungeons: dungeons[dungeon_id] = []
                dungeons[dungeon_id].append((map_id, details))
            else: standalone_maps.append((map_id, details))

        for dungeon_id in sorted(dungeons.keys()):
            dungeon_maps = dungeons[dungeon_id]
            dungeon_name = dungeon_id
            for map_id, details in dungeon_maps:
                if "entrance" in map_id:
                    dungeon_name = details.get("name", dungeon_id)
                    break
            
            parent_item = self.maps_tree.insert("", "end", text=f"📁 {dungeon_name}", open=False, iid=dungeon_id)
            
            def sort_key(map_tuple):
                map_id = map_tuple[0]
                if "entrance" in map_id: return (0, map_id)
                parts = map_id.split('_')
                if parts[-1].endswith('f'):
                    try:
                        return (1, int(parts[-1][:-1]))
                    except (ValueError, IndexError): pass
                return (2, map_id)
            dungeon_maps.sort(key=sort_key)

            for map_id, details in dungeon_maps:
                self.maps_tree.insert(parent_item, "end", text=details.get("name", map_id), iid=map_id)
        for map_id, details in sorted(standalone_maps):
             self.maps_tree.insert("", "end", text=details.get("name", map_id), iid=map_id)

    def on_map_select(self, event): pass

    def load_selected_map(self):
        selected_id = self.maps_tree.selection()
        if not selected_id or selected_id[0] not in self.maps_data: return
        self.current_map_id = selected_id[0]
        self.display_map_details(self.current_map_id)

    def create_new_map(self):
        new_map_id = simpledialog.askstring("新地圖", "為新地圖輸入一個唯一的ID:")
        if new_map_id:
            if new_map_id in self.maps_data:
                messagebox.showerror("錯誤", "具有此ID的地圖已存在。")
                return
            self.current_map_id = new_map_id
            self.maps_data[self.current_map_id] = {"name": "新地圖", "tier": 1, "world": "", "area": "", "layout": ["...", ".P.", "..."], "legend": {}, "exits": {}, "monsters": [], "treasure_rewards": {}}
            self.populate_maps_list()
            if self.maps_tree.exists(self.current_map_id):
                self.maps_tree.selection_set(self.current_map_id)
                self.maps_tree.see(self.current_map_id)
            self.display_map_details(self.current_map_id)

    def save_current_map(self):
        if not self.current_map_id:
            messagebox.showerror("錯誤", "目前沒有載入地圖。")
            return
        try:
            map_data = self.maps_data[self.current_map_id]
            new_map_id = self.detail_widgets["map_id_var"].get()
            if new_map_id != self.current_map_id:
                if new_map_id in self.maps_data:
                    messagebox.showerror("錯誤", f"地圖ID '{new_map_id}' 已存在。")
                    self.detail_widgets["map_id_var"].set(self.current_map_id)
                    return
                self.maps_data[new_map_id] = self.maps_data.pop(self.current_map_id)
                self.current_map_id = new_map_id
            
            map_data["name"] = self.detail_widgets["name_var"].get()
            map_data["world"] = self.detail_widgets["world_var"].get()
            map_data["area"] = self.detail_widgets["area_var"].get()
            map_data["tier"] = int(self.detail_widgets["tier_var"].get())
            map_data["dungeon_id"] = self.detail_widgets["dungeon_id_var"].get()
            map_data["hidden_in_menu"] = self.detail_widgets["hidden_in_menu_var"].get()
            
            start_pos_str = self.detail_widgets["start_pos_var"].get()
            if start_pos_str: map_data["start_pos"] = json.loads(f"[{start_pos_str}]")
            elif "start_pos" in map_data: del map_data["start_pos"]

            cost = int(self.detail_widgets["entry_cost_money_var"].get() or 0)
            if cost > 0: map_data["entry_cost_money"] = cost
            elif "entry_cost_money" in map_data: del map_data["entry_cost_money"]

            limit = int(self.detail_widgets["daily_limit_var"].get() or 0)
            if limit > 0: map_data["daily_limit"] = limit
            elif "daily_limit" in map_data: del map_data["daily_limit"]

            map_data["layout"] = ["".join(var.get() or "." for var in row) for row in self.detail_widgets.get("layout_grid", [])]
            
            legend_tree = self.detail_widgets.get("legend_tree")
            if legend_tree:
                map_data["legend"] = {legend_tree.item(i)["values"][0]: legend_tree.item(i)["values"][1] for i in legend_tree.get_children()}

            monsters_tree = self.detail_widgets.get("monsters_tree")
            if monsters_tree:
                map_data["monsters"] = [{"name": v[0], "reinforcement_rate": float(v[1])} for i in monsters_tree.get_children() if (v := monsters_tree.item(i)["values"])]

            treasure_money = int(self.detail_widgets["treasure_money_var"].get() or 0)
            treasure_items_tree = self.detail_widgets.get("treasure_items_tree")
            treasure_items = {}
            if treasure_items_tree:
                treasure_items = {v[0]: int(v[1]) for i in treasure_items_tree.get_children() if (v := treasure_items_tree.item(i)["values"])}
            if treasure_money > 0 or treasure_items: map_data["treasure_rewards"] = {"money": treasure_money, "items": treasure_items}
            elif "treasure_rewards" in map_data: del map_data["treasure_rewards"]

            exits_tree = self.detail_widgets.get("exits_tree")
            if exits_tree:
                 map_data["exits"] = {v[0]: {"target_map_id": v[1], "target_pos": [int(p.strip()) for p in v[2].split(',')] } for i in exits_tree.get_children() if (v := exits_tree.item(i)["values"])}

            reward_exits_list = []
            reward_exits_tree = self.detail_widgets.get("reward_exits_tree")
            if reward_exits_tree:
                for item_id in reward_exits_tree.get_children():
                    full_data = getattr(reward_exits_tree, item_id, None)
                    if full_data: reward_exits_list.append(full_data)
            map_data["reward_exits"] = reward_exits_list

            messagebox.showinfo("成功", f"地圖 '{self.current_map_id}' 已在記憶體中更新。")
            self.populate_maps_list()
            if self.maps_tree.exists(self.current_map_id):
                self.maps_tree.selection_set(self.current_map_id)
                self.maps_tree.see(self.current_map_id)
        except Exception as e: messagebox.showerror("錯誤", f"儲存時發生錯誤: {e}")

    def delete_selected_map(self):
        selected_id = self.maps_tree.selection()
        if not selected_id: return
        map_id_to_delete = selected_id[0]
        if map_id_to_delete not in self.maps_data:
            messagebox.showerror("錯誤", "無法刪除地城資料夾，請單獨刪除地圖。")
            return
        if messagebox.askyesno("確認", f"您確定要刪除 '{map_id_to_delete}' 嗎？此操作無法復原。"):
            del self.maps_data[map_id_to_delete]
            self.populate_maps_list()
            self.clear_details_panel()

    def display_map_details(self, map_id):
        for tab in [self.tab_main, self.tab_layout, self.tab_entities]:
            for widget in tab.winfo_children(): widget.destroy()
        map_data = self.maps_data.get(map_id, {})
        self.setup_main_details_tab(self.tab_main, map_id, map_data)
        self.setup_layout_legend_tab(self.tab_layout, map_data)
        self.setup_entities_tab(self.tab_entities, map_data)

    def setup_main_details_tab(self, parent_tab, map_id, map_data):
        details_frame = ttk.Frame(parent_tab); details_frame.pack(fill='x', padx=10, pady=10)
        details_frame.columnconfigure(1, weight=1)
        def create_entry(row, label, val):
            ttk.Label(details_frame, text=label).grid(row=row, column=0, sticky="w", padx=5, pady=2)
            var = tk.StringVar(value=val); ttk.Entry(details_frame, textvariable=var).grid(row=row, column=1, sticky="ew", padx=5, pady=2)
            return var
        self.detail_widgets["map_id_var"] = create_entry(0, "地圖ID:", map_id)
        self.detail_widgets["name_var"] = create_entry(1, "名稱:", map_data.get("name", ""))
        self.detail_widgets["world_var"] = create_entry(2, "世界:", map_data.get("world", ""))
        self.detail_widgets["area_var"] = create_entry(3, "地區:", map_data.get("area", ""))
        self.detail_widgets["tier_var"] = create_entry(4, "階級:", map_data.get("tier", 1))
        self.detail_widgets["dungeon_id_var"] = create_entry(5, "地城ID:", map_data.get("dungeon_id", ""))
        self.detail_widgets["entry_cost_money_var"] = create_entry(6, "入場金額:", map_data.get("entry_cost_money", ""))
        self.detail_widgets["daily_limit_var"] = create_entry(7, "每日限制:", map_data.get("daily_limit", ""))
        pos = map_data.get("start_pos", []); self.detail_widgets["start_pos_var"] = create_entry(8, "起始位置 (x,y):", f"{pos[0]},{pos[1]}" if len(pos) == 2 else "")
        ttk.Label(details_frame, text="在選單中隱藏:").grid(row=9, column=0, sticky="w", padx=5, pady=2)
        hidden_var = tk.BooleanVar(value=map_data.get("hidden_in_menu", False))
        ttk.Checkbutton(details_frame, variable=hidden_var).grid(row=9, column=1, sticky="w", padx=5, pady=2)
        self.detail_widgets["hidden_in_menu_var"] = hidden_var

    def setup_layout_legend_tab(self, parent_tab, map_data):
        self.setup_layout_editor(parent_tab, map_data)
        self.setup_legend_editor(parent_tab, map_data)

    def setup_layout_editor(self, parent_tab, map_data):
        f = ttk.LabelFrame(parent_tab, text="地圖佈局"); f.pack(fill="both", expand=True, padx=10, pady=5)
        cf = ttk.Frame(f); cf.pack(fill="x", pady=5)
        ttk.Label(cf, text="寬度:").pack(side="left"); wv = tk.StringVar(); self.detail_widgets["layout_width_var"] = wv
        ttk.Entry(cf, textvariable=wv, width=5).pack(side="left")
        ttk.Label(cf, text="高度:").pack(side="left", padx=(10, 5)); hv = tk.StringVar(); self.detail_widgets["layout_height_var"] = hv
        ttk.Entry(cf, textvariable=hv, width=5).pack(side="left")
        ttk.Button(cf, text="調整尺寸", command=self.resize_layout_grid).pack(side="left", padx=10)
        c = tk.Canvas(f); c.pack(side="left", fill="both", expand=True)
        sy = ttk.Scrollbar(f, orient="vertical", command=c.yview); sy.pack(side="right", fill="y"); c.configure(yscrollcommand=sy.set)
        sx = ttk.Scrollbar(f, orient="horizontal", command=c.xview); sx.pack(side="bottom", fill="x"); c.configure(xscrollcommand=sx.set)
        self.grid_frame = ttk.Frame(c); c.create_window((0, 0), window=self.grid_frame, anchor="nw")
        self.grid_frame.bind("<Configure>", lambda e: c.configure(scrollregion=c.bbox("all")))
        self.load_grid_from_data(map_data.get("layout", []))

    def load_grid_from_data(self, layout_data):
        for w in self.grid_frame.winfo_children(): w.destroy()
        self.detail_widgets["layout_grid"] = []
        h = len(layout_data); w = len(layout_data[0]) if h > 0 else 0
        self.detail_widgets["layout_width_var"].set(str(w)); self.detail_widgets["layout_height_var"].set(str(h))
        for r, row_str in enumerate(layout_data):
            row_widgets = []
            for c, char in enumerate(row_str):
                var = tk.StringVar(value=char)
                entry = ttk.Entry(self.grid_frame, textvariable=var, width=3, justify="center", font=('Courier', 14))
                entry.grid(row=r, column=c, padx=1, pady=1); row_widgets.append(var)
            self.detail_widgets["layout_grid"].append(row_widgets)

    def resize_layout_grid(self):
        try: w, h = int(self.detail_widgets["layout_width_var"].get()), int(self.detail_widgets["layout_height_var"].get())
        except ValueError: messagebox.showerror("錯誤", "寬度和高度必須是有效的整數。"); return
        old_vars = self.detail_widgets.get("layout_grid", [])
        oh = len(old_vars); ow = len(old_vars[0]) if oh > 0 else 0
        new_data = ["".join([(old_vars[r][c].get() or ".") if r < oh and c < ow else "." for c in range(w)]) for r in range(h)]
        self.load_grid_from_data(new_data)

    def setup_legend_editor(self, parent_tab, map_data):
        f = ttk.LabelFrame(parent_tab, text="圖例"); f.pack(fill="x", padx=10, pady=5)
        t = ttk.Treeview(f, columns=("字元", "表情符號名稱"), show="headings", height=5); t.pack(side="left", fill="both", expand=True)
        t.heading("字元", text="字元"); t.column("字元", width=60, anchor="center")
        t.heading("表情符號名稱", text="表情符號名稱"); self.detail_widgets["legend_tree"] = t
        for c, n in map_data.get("legend", {}).items(): t.insert("", "end", values=(c, n))
        bf = ttk.Frame(f); bf.pack(side="left", padx=5, fill="y")
        ttk.Button(bf, text="新增/編輯", command=self.add_edit_legend).pack()
        ttk.Button(bf, text="移除", command=self.remove_legend).pack()

    def add_edit_legend(self):
        d = tk.Toplevel(self); d.title("新增/編輯圖例")
        ttk.Label(d, text="字元:").grid(row=0, column=0, padx=5, pady=5); cv = tk.StringVar()
        ttk.Entry(d, textvariable=cv, width=5).grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(d, text="表情符號名稱:").grid(row=1, column=0, padx=5, pady=5); nv = tk.StringVar()
        ttk.Entry(d, textvariable=nv).grid(row=1, column=1, padx=5, pady=5)
        def on_ok():
            c, n = cv.get(), nv.get()
            if not c or not n: messagebox.showerror("錯誤", "字元和名稱不能為空。"); return
            t = self.detail_widgets["legend_tree"]
            found = False
            for item_id in t.get_children():
                if t.item(item_id)["values"][0] == c:
                    t.item(item_id, values=(c, n)); found = True; break
            if not found: t.insert("", "end", values=(c, n))
            d.destroy()
        ttk.Button(d, text="確定", command=on_ok).grid(row=2, column=0, columnspan=2, pady=10)

    def remove_legend(self):
        tree = self.detail_widgets["legend_tree"]
        selected_item = tree.selection()
        if not selected_item: messagebox.showwarning("警告", "請選擇要移除的圖例項目。"); return
        tree.delete(selected_item[0])

    def setup_entities_tab(self, parent_tab, map_data):
        self.setup_monsters_editor(parent_tab, map_data)
        self.setup_treasure_editor(parent_tab, map_data)
        self.setup_exits_editor(parent_tab, map_data)
        self.setup_reward_exits_editor(parent_tab, map_data)

    def setup_reward_exits_editor(self, parent_tab, map_data):
        f = ttk.LabelFrame(parent_tab, text="獎勵出口 (終點)"); f.pack(fill="x", expand=True, padx=10, pady=5)
        t = ttk.Treeview(f, columns=("字元", "目標地圖ID", "訊息"), show="headings", height=4); t.pack(side="left", fill="x", expand=True)
        t.heading("字元", text="字元"); t.column("字元", width=80, anchor="center")
        t.heading("目標地圖ID", text="目標地圖ID"); t.heading("訊息", text="訊息"); self.detail_widgets["reward_exits_tree"] = t
        for i, ed in enumerate(map_data.get("reward_exits", [])):
            item_id = f"re_{i}"; t.insert("", "end", iid=item_id, values=(ed.get("char",""), ed.get("target_map_id",""), ed.get("message",""))); setattr(t, item_id, ed)
        bf = ttk.Frame(f); bf.pack(side="left", padx=5)
        ttk.Button(bf, text="新增", command=self.add_reward_exit).pack(fill="x")
        ttk.Button(bf, text="編輯", command=self.edit_reward_exit).pack(fill="x")
        ttk.Button(bf, text="移除", command=self.remove_reward_exit).pack(fill="x")

    def add_reward_exit(self): self.show_reward_exit_dialog()
    def edit_reward_exit(self):
        t = self.detail_widgets["reward_exits_tree"]; s = t.selection()
        if not s: messagebox.showwarning("警告", "請選擇要編輯的獎勵出口。"); return
        self.show_reward_exit_dialog(existing_data=getattr(t, s[0], None), item_id=s[0])
    def remove_reward_exit(self):
        t = self.detail_widgets["reward_exits_tree"]; s = t.selection()
        if s: t.delete(s[0])

    def show_reward_exit_dialog(self, existing_data=None, item_id=None):
        d = tk.Toplevel(self); d.title("新增/編輯獎勵出口"); ed = existing_data or {}
        mf = ttk.Frame(d); mf.pack(padx=10, pady=10)
        
        ttk.Label(mf, text="字元:").grid(row=0, column=0, sticky="w", pady=2); cv = tk.StringVar(value=ed.get("char", "")); ttk.Entry(mf, textvariable=cv).grid(row=0, column=1, sticky="ew")
        ttk.Label(mf, text="目標地圖ID:").grid(row=1, column=0, sticky="w", pady=2); tv = tk.StringVar(value=ed.get("target_map_id", "")); ttk.Entry(mf, textvariable=tv).grid(row=1, column=1, sticky="ew")
        pos = ed.get("target_pos", []); ps = f"{pos[0]},{pos[1]}" if len(pos) == 2 else ""
        ttk.Label(mf, text="目標位置 (x,y):").grid(row=2, column=0, sticky="w", pady=2); pv = tk.StringVar(value=ps); ttk.Entry(mf, textvariable=pv).grid(row=2, column=1, sticky="ew")
        ttk.Label(mf, text="訊息:").grid(row=3, column=0, sticky="w", pady=2); mv = tk.StringVar(value=ed.get("message", "")); ttk.Entry(mf, textvariable=mv).grid(row=3, column=1, sticky="ew")
        
        rf = ttk.LabelFrame(mf, text="獎勵"); rf.grid(row=4, column=0, columnspan=2, sticky="ew", pady=5)
        r_data = ed.get("rewards", {})
        ttk.Label(rf, text="金錢:").grid(row=0, column=0, sticky="w"); money_v = tk.StringVar(value=r_data.get("money", 0)); ttk.Entry(rf, textvariable=money_v).grid(row=0, column=1)
        ttk.Label(rf, text="經驗:").grid(row=1, column=0, sticky="w"); exp_v = tk.StringVar(value=r_data.get("exp", 0)); ttk.Entry(rf, textvariable=exp_v).grid(row=1, column=1)
        
        itf = ttk.LabelFrame(rf, text="物品"); itf.grid(row=2, column=0, columnspan=2, sticky="ew", pady=5)
        it = ttk.Treeview(itf, columns=("名稱", "數量"), show="headings", height=3); it.pack(side="left", fill="both", expand=True)
        it.heading("名稱", text="名稱"); it.heading("數量", text="數量"); it.column("數量", width=60, anchor="center")
        for n, q in r_data.get("items", {}).items(): it.insert("", "end", values=(n, q))
        bf = ttk.Frame(itf); bf.pack(side="left", fill="y", padx=5)
        def add_item(): self._show_item_dialog(d, it)
        ttk.Button(bf, text="新增/編輯", command=add_item).pack()
        remove_button = ttk.Button(bf, text="移除", command=lambda: it.delete(it.selection()[0]) if it.selection() else None)
        remove_button.pack()

        def on_ok():
            try:
                items = {v[0]: int(v[1]) for i in it.get_children() if (v:=it.item(i)["values"])}
                new_data = {"char": cv.get(), "target_map_id": tv.get(), "target_pos": [int(p.strip()) for p in pv.get().split(',')], "message": mv.get(), "rewards": {"money": int(money_v.get() or 0), "exp": int(exp_v.get() or 0), "items": items}}
                if not new_data["char"]: messagebox.showerror("錯誤", "字元不可為空。"); return
                t = self.detail_widgets["reward_exits_tree"]
                if item_id: t.item(item_id, values=(new_data["char"], new_data["target_map_id"], new_data["message"])); setattr(t, item_id, new_data)
                else: new_id = f"re_{len(t.get_children())}"; t.insert("", "end", iid=new_id, values=(new_data["char"], new_data["target_map_id"], new_data["message"])); setattr(t, new_id, new_data)
                d.destroy()
            except Exception: messagebox.showerror("錯誤", "輸入無效。請檢查數字和位置格式。")
        ttk.Button(mf, text="確定", command=on_ok).grid(row=5, column=0, columnspan=2, pady=10)

    def _show_item_dialog(self, parent, tree):
        d = tk.Toplevel(parent); d.title("新增/編輯物品")
        ttk.Label(d, text="物品名稱:").grid(row=0, column=0, padx=5, pady=5); nv = tk.StringVar(); ttk.Entry(d, textvariable=nv).grid(row=0, column=1)
        ttk.Label(d, text="數量:").grid(row=1, column=0, padx=5, pady=5); qv = tk.StringVar(); ttk.Entry(d, textvariable=qv).grid(row=1, column=1)
        def on_ok():
            n, q = nv.get(), qv.get()
            if not n or not q: messagebox.showerror("錯誤", "名稱和數量不能為空。", parent=d); return
            try: int(q)
            except ValueError: messagebox.showerror("錯誤", "數量必須是有效的整數。", parent=d); return
            found = False
            for item_id in tree.get_children():
                if tree.item(item_id)["values"][0] == n:
                    tree.item(item_id, values=(n,q)); found = True; break
            if not found: tree.insert("", "end", values=(n, q))
            d.destroy()
        ttk.Button(d, text="確定", command=on_ok).grid(row=2, column=0, columnspan=2, pady=10)

    def setup_exits_editor(self, parent_tab, map_data):
        f = ttk.LabelFrame(parent_tab, text="出口 (傳送點)"); f.pack(fill="x", expand=True, padx=10, pady=5)
        t = ttk.Treeview(f, columns=("字元", "目標地圖ID", "目標位置"), show="headings", height=4); t.pack(side="left", fill="x", expand=True)
        t.heading("字元", text="字元"); t.column("字元", width=80, anchor="center")
        t.heading("目標地圖ID", text="目標地圖ID"); t.heading("目標位置", text="目標位置"); t.column("目標位置", width=100, anchor="center")
        self.detail_widgets["exits_tree"] = t
        for c, d in map_data.get("exits", {}).items():
            pos = f"{d.get('target_pos', ['',''])[0]}, {d.get('target_pos', ['',''])[1]}"
            t.insert("", "end", values=(c, d.get("target_map_id", ""), pos))
        bf = ttk.Frame(f); bf.pack(side="left", padx=5)
        ttk.Button(bf, text="新增", command=self.add_exit).pack(fill="x")
        ttk.Button(bf, text="編輯", command=self.edit_exit).pack(fill="x")
        ttk.Button(bf, text="移除", command=self.remove_exit).pack(fill="x")

    def add_exit(self): self.show_exit_dialog()
    def edit_exit(self):
        t = self.detail_widgets["exits_tree"]; s = t.selection()
        if not s: messagebox.showwarning("警告", "請選擇要編輯的出口。"); return
        self.show_exit_dialog(existing_values=t.item(s[0])["values"], item_id=s[0])
    def remove_exit(self):
        t = self.detail_widgets["exits_tree"]; s = t.selection()
        if s: t.delete(s[0])

    def show_exit_dialog(self, existing_values=None, item_id=None):
        d = tk.Toplevel(self); d.title("新增/編輯出口"); ev = existing_values or ["", "", ""]
        ttk.Label(d, text="字元:").grid(row=0, column=0, padx=5, pady=5, sticky="w"); cv = tk.StringVar(value=ev[0]); ttk.Entry(d, textvariable=cv).grid(row=0, column=1)
        ttk.Label(d, text="目標地圖ID:").grid(row=1, column=0, padx=5, pady=5, sticky="w"); mv = tk.StringVar(value=ev[1]); ttk.Entry(d, textvariable=mv).grid(row=1, column=1)
        ttk.Label(d, text="目標位置 (x,y):").grid(row=2, column=0, padx=5, pady=5, sticky="w"); pv = tk.StringVar(value=ev[2]); ttk.Entry(d, textvariable=pv).grid(row=2, column=1)
        def on_ok():
            c, tid, pos = cv.get(), mv.get(), pv.get()
            if not all([c, tid, pos]): messagebox.showerror("錯誤", "所有欄位皆為必填。"); return
            if item_id: self.detail_widgets["exits_tree"].item(item_id, values=(c, tid, pos))
            else:
                if any(c == self.detail_widgets["exits_tree"].item(i)["values"][0] for i in self.detail_widgets["exits_tree"].get_children()):
                    messagebox.showerror("錯誤", f"出口字元 '{c}' 已存在。"); return
                self.detail_widgets["exits_tree"].insert("", "end", values=(c, tid, pos))
            d.destroy()
        ttk.Button(d, text="確定", command=on_ok).grid(row=3, column=0, columnspan=2, pady=10)

    def setup_treasure_editor(self, parent_tab, map_data):
        f = ttk.LabelFrame(parent_tab, text="寶箱獎勵"); f.pack(fill="x", expand=True, padx=10, pady=5)
        td = map_data.get("treasure_rewards", {})
        mf = ttk.Frame(f); mf.pack(fill="x", padx=5, pady=2)
        ttk.Label(mf, text="金錢:").pack(side="left"); mv = tk.StringVar(value=td.get("money", "0"))
        ttk.Entry(mf, textvariable=mv, width=10).pack(side="left"); self.detail_widgets["treasure_money_var"] = mv
        itf = ttk.Frame(f); itf.pack(fill="both", expand=True, padx=5, pady=5)
        t = ttk.Treeview(itf, columns=("物品名稱", "數量"), show="headings", height=4); t.pack(side="left", fill="both", expand=True)
        t.heading("物品名稱", text="物品名稱"); t.heading("數量", text="數量"); t.column("數量", width=60, anchor="center")
        self.detail_widgets["treasure_items_tree"] = t
        for n, q in td.get("items", {}).items(): t.insert("", "end", values=(n, q))
        bf = ttk.Frame(itf); bf.pack(side="left", padx=5, fill="y")
        ttk.Button(bf, text="新增/編輯", command=self.add_edit_treasure_item).pack()
        ttk.Button(bf, text="移除", command=self.remove_treasure_item).pack()

    def add_edit_treasure_item(self):
        d = tk.Toplevel(self); d.title("新增/編輯獎勵物品")
        ttk.Label(d, text="物品名稱:").grid(row=0, column=0, padx=5, pady=5); nv = tk.StringVar(); ttk.Entry(d, textvariable=nv).grid(row=0, column=1)
        ttk.Label(d, text="數量:").grid(row=1, column=0, padx=5, pady=5); qv = tk.StringVar(); ttk.Entry(d, textvariable=qv).grid(row=1, column=1)
        def on_ok():
            n, q = nv.get(), qv.get()
            if not n or not q: messagebox.showerror("錯誤", "名稱和數量不能為空。"); return
            try: int(q)
            except ValueError: messagebox.showerror("錯誤", "數量必須是有效的整數。"); return
            t = self.detail_widgets["treasure_items_tree"]
            found = False
            for item_id in t.get_children():
                if t.item(item_id)["values"][0] == n:
                    t.item(item_id, values=(n, q)); found = True; break
            if not found: t.insert("", "end", values=(n, q))
            d.destroy()
        ttk.Button(d, text="確定", command=on_ok).grid(row=2, column=0, columnspan=2, pady=10)

    def remove_treasure_item(self):
        t = self.detail_widgets["treasure_items_tree"]
        s = t.selection()
        if not s: messagebox.showwarning("警告", "請選擇要移除的物品。"); return
        t.delete(s[0])

    def setup_monsters_editor(self, parent_tab, map_data):
        f = ttk.LabelFrame(parent_tab, text="怪物"); f.pack(fill="x", expand=True, padx=10, pady=5)
        t = ttk.Treeview(f, columns=("名稱", "強化率"), show="headings", height=5); t.pack(side="left", fill="x", expand=True)
        t.heading("名稱", text="名稱"); t.heading("強化率", text="強化率"); self.detail_widgets["monsters_tree"] = t
        for m in map_data.get("monsters", []): t.insert("", "end", values=(m.get("name", ""), m.get("reinforcement_rate", 1.0)))
        bf = ttk.Frame(f); bf.pack(side="left", padx=5)
        ttk.Button(bf, text="新增", command=self.add_monster).pack(fill="x")
        ttk.Button(bf, text="編輯", command=self.edit_monster).pack(fill="x")
        ttk.Button(bf, text="移除", command=self.remove_monster).pack(fill="x")

    def add_monster(self): self.show_monster_dialog()
    def edit_monster(self):
        t = self.detail_widgets["monsters_tree"]; s = t.selection()
        if not s: messagebox.showwarning("警告", "請選擇要編輯的怪物。"); return
        self.show_monster_dialog(existing_values=t.item(s[0])["values"], item_id=s[0])
    def remove_monster(self):
        t = self.detail_widgets["monsters_tree"]; s = t.selection()
        if s: t.delete(s[0])
        else: messagebox.showwarning("警告", "請選擇要移除的怪物。")

    def show_monster_dialog(self, existing_values=None, item_id=None):
        d = tk.Toplevel(self); d.title("新增/編輯怪物"); ev = existing_values or ["", "1.0"]
        ttk.Label(d, text="名稱:").grid(row=0, column=0, padx=5, pady=5); nv = tk.StringVar(value=ev[0]); ttk.Entry(d, textvariable=nv).grid(row=0, column=1)
        ttk.Label(d, text="強化率:").grid(row=1, column=0, padx=5, pady=5); rv = tk.StringVar(value=ev[1]); ttk.Entry(d, textvariable=rv).grid(row=1, column=1)
        def on_ok():
            try:
                n, r = nv.get(), float(rv.get())
                if not n: messagebox.showerror("錯誤", "名稱不可為空。"); return
                if item_id: self.detail_widgets["monsters_tree"].item(item_id, values=(n, r))
                else: self.detail_widgets["monsters_tree"].insert("", "end", values=(n, r))
                d.destroy()
            except ValueError: messagebox.showerror("錯誤", "強化率必須是一個有效的數字。")
        ttk.Button(d, text="確定", command=on_ok).grid(row=2, column=0, columnspan=2, pady=10)

    def clear_details_panel(self):
        for tab in [self.tab_main, self.tab_layout, self.tab_entities]:
            for widget in tab.winfo_children(): widget.destroy()
        self.current_map_id = None
        ttk.Label(self.tab_main, text="請選擇一個地圖並點擊 '讀取選擇' 來查看詳細資訊。").pack(pady=20)

if __name__ == "__main__":
    app = MapEditor()
    app.mainloop()
