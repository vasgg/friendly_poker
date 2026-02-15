# fmt: off
texts = {
    'abort_game_dialog': 'Abort game {}. Confirm?',
    'abort_game_reply': 'Game {} aborted.',
    'admin_menu': 'Select an action.',
    'admin_game_created': 'Game {} started.',
    'admin_players_added': 'Added {} players to game {}.',
    'admin_1000_added_to_players': 'Game {}. Added 1000 to {} players:\n\n<b>{}</b>',
    'admin_players_with_0': 'Game {}. BUY-OUT set to 0 for {} players.',
    'admin_players_with_0_dialog': 'Select players for BUY-OUT = 0.',
    'admin_players_buyout_dialog': 'Select player for BUY-OUT.',
    'admin_set_buyout_dialog': 'Enter BUY-OUT for {}.',
    'admin_statistics': 'Not available yet.',
    'user_statistics': 'Not available yet.',
    'admin_delete_player_dialog': 'Select player to delete.',
    'admin_delete_player_no_players': 'No players available. Try again later.',
    'admin_delete_player_summary_header': '<b>Delete player:</b> {}',
    'admin_delete_player_summary_debts_header': '<b>Active debts</b>',
    'admin_delete_player_summary_no_debts': 'No active debts.',
    'admin_delete_player_summary_owes': '\n<b>Owes</b>',
    'admin_delete_player_summary_owed': '\n<b>Owed to player</b>',
    'admin_delete_player_confirm': 'Delete <b>{}</b>?',
    'admin_delete_player_blocked_active_game': 'Cannot delete <b>{}</b>. Active game <b>{:02}</b>. Finish it first.',
    'admin_delete_player_blocked_admin': 'Cannot delete admins or yourself. Select another player.',
    'admin_delete_player_blocked_bot': 'Cannot delete the bot. Select another player.',
    'admin_delete_player_deleted': '<b>{}</b> deleted.',
    'admin_delete_player_cancelled': 'Deletion cancelled.',
    'admin_delete_player_group_result': 'Group removal: {}.',
    'admin_delete_player_report_header': '<b>Delete player report</b>',
    'admin_delete_player_report_results': '<b>Results</b>',
    'admin_delete_player_report_debts': 'Debts removed: {}',
    'admin_delete_player_report_records': 'Records removed: {}',
    'admin_delete_player_report_host': 'Host reassigned in games: {}',
    'admin_delete_player_report_mvp': 'MVP recalculated in games: {}',
    'admin_delete_player_report_pot': 'Total pot recalculated in games: {}',
    'delete_player_notify_header': '<b>Player removed</b>',
    'delete_player_notify_body': 'Player <b>{}</b> removed from chat and group. Related debts removed from stats.',
    'delete_player_notify_details_header': '<b>Debt details</b>',
    'admin_private_only': 'Use /admin in private chat.',
    'admin_menu_header': '<b>Admin panel</b>',
    'admin_menu_status_active': 'Status: <b>Active</b>',
    'admin_menu_status_idle': 'Status: <b>Idle</b>',
    'admin_menu_game_line': 'Game: <b>{:02}</b>',
    'admin_menu_host_line': 'Host: <b>{}</b>',
    'admin_menu_players_line': 'Players: <b>{}</b>',
    'admin_menu_total_pot_line': 'Total pot: <b>{}</b>',
    'admin_menu_hint': 'Select an action below.',
    'admin_next_game_menu': 'Extras.',
    'host_not_selected': 'Host not selected. Start again.',
    'info_message': '<b>Bot info</b>\n\n'
                    '<b>Commands</b>\n'
                    '/settings — payment requisites\n'
                    '/stats — stats\n'
                    '/admin — admin panel\n'
                    '<b>Support</b>\n'
                    'Support the creator via card transfer:\n'
                    '<b>Bank of Georgia</b> <code>{}</code>\n'
                    '<b>Name:</b> <code>{}</code>',
    'insufficient_privileges': 'Not allowed. Admins only.',
    'choose_host': 'Select host.',
    'incorrect_buyout_value': 'Invalid BUY-OUT. Enter a number.',
    'game_already_active': 'Active game exists. Finish it first.',
    'no_active_game': 'No active game. Start one first.',
    'select_mode_prompt': 'Select ratio for the next game.',
    'ratio_set': 'Next game ratio: x{}.',
    'yearly_stats_set': 'Yearly stats will be sent after the next game.',

    'add_funds_selector': 'Select add-funds mode.',
    'add_funds_multiselect': 'Select players to add 1000.',
    'add_funds_to_single_player': 'Select player to add funds.',
    'custom_funds_amount_prompt': 'Enter custom BUY-IN for {}.',
    'custom_funds_confirm': 'Add <b>{}</b> to <b>{}</b>?',
    'custom_funds_applied': 'Game {}. Added {} to {}. BUY-IN: {}.',
    'custom_funds_invalid': 'Invalid amount. Enter a number.',
    'custom_funds_not_ready': 'Player not selected. Start again.',
    'check_game_balance_error': 'Balance check failed. Try again.',
    'game_started_group': 'Game <b>{game_id:02d}</b> started with <b>{players_count}</b> players.\n'
                          'Host: <b>{host_name}</b>.',
    'finish_game_dialog': 'Select an action.',
    'buy_out_updated': 'Game {}. {} BUY-OUT set to {}.',
    'remained_players': 'Game {}. Players without BUY-OUT: {}.',
    'exit_game_wrong_total_sum>0': 'Cannot finish game: buy-in and cash-out do not match.\n'
                                   'Fewer chips returned.\n\n'
                                   'Total pot: {}\n'
                                   'Difference: <b>{}</b>',
    'exit_game_wrong_total_sum<0': 'Cannot finish game: buy-in and cash-out do not match.\n'
                                   'Too many chips declared.\n\n'
                                   'Total pot: {}\n'
                                   'Difference: <b>{}</b>',
    'global_game_report': 'Game <b>{:02}</b> ended.\n\n'
                          'Duration: <b>{}</b>\n'
                          'Total pot: <b>{}</b>\n'
                          'MVP: <b>{}</b> (ROI: <b>{:.2f}%</b>)',
    'debtor_personal_game_report': 'Game <b>{:02}</b>. Debt <b>#{}</b>.\n\n'
                                   'You owe <b>{:.2f} GEL</b> to <b>{}</b>.',
    'debtor_personal_game_report_with_requisites': 'Game <b>{:02}</b>. Debt <b>#{}</b>.\n\n'
                                                   'You owe <b>{:.2f} GEL</b> to <b>{}</b>.\n\n'
                                                   '<b>Requisites</b>\n'
                                                   '<b>Bank:</b> <code>{}</code>\n'
                                                   '<b>IBAN:</b> <code>{}</code>\n'
                                                   '<b>Name:</b> <code>{}</code>',
    'creditor_personal_game_report': 'Game <b>{:02}</b>. Debt <b>#{}</b>.\n\n'
                                     '<b>{}</b> owes you <b>{:.2f} GEL</b>.',
    'debt_marked_as_paid': 'Game <b>{:02}</b>. Debt <b>#{}</b>.\n\n'
                           '<b>{}</b> marked as paid. Amount: <b>{:.2f} GEL</b>.\n'
                           'Confirm payment?',
    'debt_complete': 'Game <b>{:02}</b>. Debt <b>#{}</b>.\n\n'
                     '<b>{}</b> marked as paid. Amount: <b>{:.2f} GEL</b>.',
    'debt_marked_as_paid_confirmation': 'Game <b>{:02}</b>. Debt <b>#{}</b>.\n\n'
                                        'Payment of <b>{:.2f} GEL</b> to <b>{}</b> sent for confirmation.',
    'debt_complete_confirmation': 'Game <b>{:02}</b>. Debt <b>#{}</b>.\n\n'
                                  'Payment of <b>{:.2f} GEL</b> from <b>{}</b> confirmed.',
    'debt_incomplete': 'Game <b>{:02}</b>. Debt <b>#{}</b>.\n\n'
                       '<b>{}</b> marked as unpaid.',
    'settings_updated': 'Settings saved.',
    'player_stats_ingame': 'Game <b>{:02}</b> in progress.\n\n'
                           'Current BUY-IN: <b>{}</b>\n\n'
                           '<b>Stats</b>\n'
                           'Games played: <b>{}</b>\n'
                           'Games hosted: <b>{}</b>\n'
                           'MVP awards: <b>{}</b>\n'
                           'Total BUY-IN: <b>{}</b>\n'
                           'Total BUY-OUT: <b>{}</b>\n'
                           'Total ROI: <b>{}</b>',
    'player_stats_outgame': '<b>Stats</b>\n'
                            'Games played: <b>{}</b>\n'
                            'Games hosted: <b>{}</b>\n'
                            'MVP awards: <b>{}</b>\n'
                            'Total BUY-IN: <b>{}</b>\n'
                            'Total BUY-OUT: <b>{}</b>\n'
                            'Total ROI: <b>{}</b>',
    'stats_debts_header': '\n\n<b>Debts</b>',
    'stats_debts_you_owe': '\n\n<b>You owe</b>',
    'stats_debts_owed_to_you': '\n\n<b>Owed to you</b>',
    'stats_debt_line': '\n• Game {:02} ({}): <b>{:.2f} GEL</b> → {}',
    'stats_no_debts': '\n\nNo unpaid debts.',
    'stats_debt_aggregated': '\n• {}: <b>{:.2f} GEL</b>',
    'stats_debt_detail_header': '<b>Debt details</b>',
    'stats_debt_detail_i_owe': '\n\n<b>You owe</b>',
    'stats_debt_detail_owe_me': '\n\n<b>Owed to you</b>',
    'admin_stats_ingame': 'Not available yet.',
    'admin_stats_outgame': 'Not available yet.',
    'debt_remind_sent': 'Reminder sent to {}.',
    'debt_paid_notification_sent': 'Payment request sent to {}.',
    'debt_complete_notification_sent': 'Confirmation sent to {}.',
    'bot_blocked_by_user': 'User blocked the bot.',
    'photo_missing_warning': 'No photo yet. Take one or skip.',
    'start_greeting': 'Hi, {}.',
    'admin_delete_player_done_popup': 'Deleted. Check private messages.',
    'game_not_found': 'Game {:02} not found.',
    'mvp_not_found': 'MVP not found. Check game data.',

}


buttons = {
    'menu_add_players': 'Add players',
    'menu_add_funds': 'Add funds',
    'menu_finish_game': 'Finish game',
    'menu_abort_game': 'Abort game',
    'menu_start_game': 'Start game',
    'menu_statistics': 'Stats',
    'menu_new_year': 'Extras',
    'menu_select_ratio': 'Set ratio',
    'menu_select_yearly_stats': 'Yearly stats',
    'menu_delete_player': 'Delete player',
    'further_button': 'Next',
    'multi_selector': 'Add 1000',
    'single_selector': 'Custom',
    'abort_game_button': 'Abort game',
    'abort_game_button_yes': 'Yes',
    'add_players': 'Add players',
    'add_players_with_0': 'Set BUY-OUT=0',
    'add_players_buyout': 'Set BUY-OUT',
    'finalize_game': 'Finalize',
    'debt_stats_i_owe': 'I owe',
    'debt_stats_owe_me': 'Owe me',
    'debt_detail_paid': '#{:02} Paid \u2192 {}',
    'debt_detail_remind': '#{:02} Remind \u2192 {}',
    'skip_photo': 'Ignore',
    'delete_player': 'Delete',
    'delete_anyway': 'Delete anyway',
    'confirm_yes': 'Yes',
    'confirm_no': 'No',
    'page_prev': 'Prev',
    'page_next': 'Next',
    'back': 'Back',
    'cancel': 'Cancel',
}

ORDER = ["IBAN", "bank", "name_surname"]

SETTINGS_QUESTIONS = {
    'IBAN': 'Enter IBAN.',
    'bank': 'Enter bank name.',
    'name_surname': 'Enter first and last name.',
}


# fmt: on
