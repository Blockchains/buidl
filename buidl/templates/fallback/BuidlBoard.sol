// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {Ownable} from "@openzeppelin/contracts/access/Ownable.sol";

/// @title BuidlBoard
/// @notice Fallback contract used by Blockchains/buidl when Grok-authored code does not pass after the retry budget:
///         an on-chain board where anyone submits an entry (title + URI), others endorse it once each, and the
///         owner records milestones as completed.
contract BuidlBoard is Ownable {
    struct Entry {
        address author;
        string title;
        string uri;
        uint64 createdAt;
        uint32 endorsements;
        uint32 milestonesDone;
    }

    Entry[] private _entries;
    mapping(uint256 => mapping(address => bool)) public endorsed;

    event Submitted(uint256 indexed id, address indexed author, string title, string uri);
    event Endorsed(uint256 indexed id, address indexed by);
    event MilestoneCompleted(uint256 indexed id, uint32 milestone, string note);

    error EmptyTitle();
    error UnknownEntry(uint256 id);
    error AlreadyEndorsed(uint256 id, address by);
    error SelfEndorsement();

    constructor() Ownable(msg.sender) {}

    function submit(string calldata title, string calldata uri) external returns (uint256 id) {
        if (bytes(title).length == 0) revert EmptyTitle();
        id = _entries.length;
        _entries.push(Entry(msg.sender, title, uri, uint64(block.timestamp), 0, 0));
        emit Submitted(id, msg.sender, title, uri);
    }

    function endorse(uint256 id) external {
        Entry storage e = _get(id);
        if (e.author == msg.sender) revert SelfEndorsement();
        if (endorsed[id][msg.sender]) revert AlreadyEndorsed(id, msg.sender);
        endorsed[id][msg.sender] = true;
        e.endorsements += 1;
        emit Endorsed(id, msg.sender);
    }

    function completeMilestone(uint256 id, string calldata note) external onlyOwner {
        Entry storage e = _get(id);
        e.milestonesDone += 1;
        emit MilestoneCompleted(id, e.milestonesDone, note);
    }

    function entryCount() external view returns (uint256) {
        return _entries.length;
    }

    function getEntry(uint256 id) external view returns (Entry memory) {
        return _get(id);
    }

    function _get(uint256 id) private view returns (Entry storage) {
        if (id >= _entries.length) revert UnknownEntry(id);
        return _entries[id];
    }
}
