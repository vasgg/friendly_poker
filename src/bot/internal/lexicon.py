# fmt: off
texts = {
    'abort_game_dialog': 'Abort game {}. Are you sure?',
    'abort_game_reply': 'Game {} aborted.',
    'admin_menu': 'Choose an action',
    'admin_game_created': 'Game {} started.',
    'admin_players_added': 'Added {} players to game {}.',
    'admin_1000_added_to_players': 'Game {}. Added 1000 to {} players:\n\n<b>{}</b>',
    'admin_players_with_0': 'Game {}. BUY-OUT set to 0 on {} players.',
    'admin_players_with_0_dialog': 'Choose players to set BUY-OUT to 0',
    'admin_players_buyout_dialog': 'Choose player to set BUY-OUT',
    'admin_set_buyout_dialog': 'Enter BUY-OUT value for {}',
    'admin_buyout_set_reply': 'Enter BUY-OUT value for {}',
    'admin_statistics': '...',
    'user_statistics': '...',
    'insufficient_privileges': 'You can\'t perform this action.',
    'choose_host': 'Choose a host.',
    'incorrect_buyout_value': 'Incorrect BUY-OUT value.',
    'game_already_active': 'There is already an active game. Please finish it first.',
    'select_mode_prompt': 'Choose ratio for the next game.',
    'ratio_set': 'Next game ratio set to x{}.',
    'yearly_stats_set': 'Yearly stats will be shown after the next game.',

    'add_photo': 'Send me photo of the event',
    'add_funds_selector': 'Select type of add funds operation',
    'add_funds_multiselect': 'Choose players to add 1000',
    'add_funds_to_single_player': 'Choose player to add funds',
    'check_game_balance_error': 'error while finding delta of total pot and buyouts',
    'user_add_funds_reply': '',
    'game_started_group': 'The game <b>{game_id:02d}</b> with <b>{players_count}</b> players has started.\n\n'
                          'Host: <b>{host_name}</b>.',
    'finish_game_dialog': 'Choose an action',
    'buy_out_updated': 'Game {}. {} BUY-OUT set to {}.',
    'remained_players': 'Game {}. Players remained: {}.',
    'exit_game_wrong_total_sum>0': 'Impossible to finish the game, the buy-in and cash-out amounts do not match.\n'
                                   'Fewer chips returned!\n\n'
                                   'Total pot: {}\n'
                                   'Difference: <b>{}</>',
    'exit_game_wrong_total_sum<0': 'Impossible to finish the game, the buy-in and cash-out amounts do not match.\n'
                                   'Too many chips declared!\n\n'
                                   'Total pot: {}\n'
                                   'Difference: <b>{}</>',
    'global_game_report': 'Game <b>{:02}</b> has ended.\n\n'
                          'Duration: <b>{}</b>\n'
                          'Total pot: <b>{}</b>\n'
                          'MVP: <b>{}</b> (ROI: <b>{:.2f}%</b>)',
    'debtor_personal_game_report': 'GAME <b>{:02}</b>. DEBT REPORT <b>#{}</b>:\n\n'
                                   'You owe <b>{:.2f} GEL</b> to <b>{}</b>.',
    'debtor_personal_game_report_with_requisites': 'GAME <b>{:02}</b>. DEBT REPORT <b>#{}</b>:\n\n'
                                                   'You owe <b>{:.2f} GEL</b> to <b>{}</b>.\n\n'
                                                   '<b>Requisites:</b>\n'
                                                   '<b>Bank:</b> <code>{}</code>\n'
                                                   '<b>IBAN:</b> <code>{}</code>\n'
                                                   '<b>Name:</b> <code>{}</code>',
    'creditor_personal_game_report': 'GAME <b>{:02}</b>. DEBT REPORT <b>#{}</b>:\n\n'
                                     '<b>{}</b> owes you <b>{:.2f} GEL</b>.',
    'debt_marked_as_paid': 'GAME <b>{:02}</b>. DEBT REPORT <b>#{}</b>:\n\n'
                           '<b>{}</b> marked debt as paid. Amount: <b>{:.2f} GEL</b>.\n'
                           'Do you receive payment?',
    'debt_complete': 'GAME <b>{:02}</b>. DEBT REPORT <b>#{}</b>:\n\n'
                     '<b>{}</b> marked debt as paid. Amount: <b>{:.2f} GEL</b>.',
    'debt_incomplete': 'GAME {:02}. DEBT REPORT #{}:\n\n'
                       '<b>{}</b> marked debt as unpaid!\n',
    'settings_updated': 'Settings updated.',
    'player_stats_ingame': 'Game <b>{:02}</b> in progress\n\n'
                           'Current BUY-IN: <b>{}</b>\n\n'
                           '<b>Stats:</b>\n'
                           'Games played: <b>{}</b>\n'
                           'Games hosted: <b>{}</b>\n'
                           'MVP awards: <b>{}</b>\n'
                           'Total BUY-IN: <b>{}</b>\n'
                           'Total BUY-OUT: <b>{}</b>\n'
                           'Total ROI: <b>{}</b>\n',
    'player_stats_outgame': '<b>Stats:</b>\n'
                            'Games played: <b>{}</b>\n'
                            'Games hosted: <b>{}</b>\n'
                            'MVP awards: <b>{}</b>\n'
                            'Total BUY-IN: <b>{}</b>\n'
                            'Total BUY-OUT: <b>{}</b>\n'
                            'Total ROI: <b>{}</b>\n',
    'admin_stats_ingame': '',
    'admin_stats_outgame': '',

}


buttons = {
    'menu_add_players': 'Add players',
    'menu_add_funds': 'Add funds',
    'menu_add_photo': 'Add photo',
    'menu_finish_game': 'Finish game',
    'menu_abort_game': 'Abort game',
    'menu_start_game': 'Start game',
    'menu_statistics': 'Statistics',
    'menu_select_ratio': 'Choose ratio',
    'menu_select_yearly_stats': 'Yearly stats next game',
    'cancel_button': 'Cancel',
    'futher_button': 'Further',
    'multi_selector': 'Add 1000',
    'single_selector': 'Custom',
    'abort_game_button': 'Abort game',
    'abort_game_button_yes': 'Yes',
    'add_players': 'Add players',
    'add_players_with_0': 'Add players with 0',
    'add_players_buyout': 'Add players BUYOUT',
    'finalize_game': 'Finalize game',
}

ORDER = ["IBAN", "bank", "name_surname"]

SETTINGS_QUESTIONS = {
    'IBAN': 'Enter your IBAN',
    'bank': 'Enter your bank title',
    'name_surname': 'Enter your first name and last name',
}


# fmt: on
