local _, ns = ...
ns.RecipeData = {
	[2660] = { skillLine = 164, reagents = { { itemID = 2835, quantity = 1 } }, output = { itemID = 2862, quantity = 1 } },
	[2661] = { skillLine = 164, reagents = { { itemID = 2840, quantity = 6 } }, output = { itemID = 2851, quantity = 1 } },
	[2149] = { skillLine = 165, reagents = { { itemID = 2318, quantity = 2 } }, output = { itemID = 2302, quantity = 1 } },
	[7418] = { skillLine = 333, reagents = { { itemID = 10940, quantity = 1 } }, output = false },
	[7795] = { skillLine = 333, reagents = { { itemID = 6338, quantity = 1 }, { itemID = 6218, quantity = 1 } }, output = { itemID = 6339, quantity = 1 } },
	[9999] = { skillLine = 164, reagents = { { itemID = 2840, quantity = 1 } }, output = { itemID = 2857, quantity = 1 } },
}
-- RecipeScrolls: [recipe spell] = { scroll item, required skill }
ns.RecipeScrolls = {
	[9999] = { 5555, 80 },
}
ns.RecipeNames = {
	[164] = {
		["Rough Sharpening Stone"] = 2660,
		["Copper Chain Belt"] = 2661,
		["Runed Copper Belt"] = 9999,
	},
	[333] = {
		["Enchant Bracer - Minor Health"] = 7418,
		["Runed Silver Rod"] = 7795,
	},
}
